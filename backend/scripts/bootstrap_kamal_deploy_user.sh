#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  backend/scripts/bootstrap_kamal_deploy_user.sh --host HOST --ssh-user USER [options]

Bootstraps a shared Kamal deploy account on a remote server by:
  - creating the deploy group and user (default: deploy)
  - adding that user to the docker group
  - seeding /home/<deploy-user>/.ssh/authorized_keys from the current remote SSH user
  - preparing /var/lib/btaa-geospatial-api for shared bind mounts
  - creating an Elasticsearch bind-mount directory with group-write access for GID 0

Options:
  --host HOST                          Remote hostname
  --ssh-user USER                      Existing remote SSH user with passwordless sudo
  --ssh-port PORT                      SSH port (default: 22)
  --deploy-user USER                   Shared deploy user to create (default: deploy)
  --shared-dir PATH                    Shared data directory (default: /var/lib/btaa-geospatial-api)
  --seed-remote-authorized-keys PATH   Remote authorized_keys path to copy from
                                       (default: .ssh/authorized_keys)
  -h, --help                           Show this help
EOF
}

host=""
ssh_user=""
ssh_port="22"
deploy_user="deploy"
shared_dir="/var/lib/btaa-geospatial-api"
seed_remote_authorized_keys=".ssh/authorized_keys"

while (($# > 0)); do
  case "$1" in
    --host)
      host="${2:-}"
      shift 2
      ;;
    --ssh-user)
      ssh_user="${2:-}"
      shift 2
      ;;
    --ssh-port)
      ssh_port="${2:-}"
      shift 2
      ;;
    --deploy-user)
      deploy_user="${2:-}"
      shift 2
      ;;
    --shared-dir)
      shared_dir="${2:-}"
      shift 2
      ;;
    --seed-remote-authorized-keys)
      seed_remote_authorized_keys="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$host" || -z "$ssh_user" ]]; then
  usage >&2
  exit 1
fi

ssh_target="${ssh_user}@${host}"

echo "Bootstrapping ${deploy_user}@${host} via ${ssh_target}..."

ssh \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=accept-new \
  -p "$ssh_port" \
  "$ssh_target" \
  "DEPLOY_USER=$(printf '%q' "$deploy_user") SHARED_DIR=$(printf '%q' "$shared_dir") SEED_KEYS=$(printf '%q' "$seed_remote_authorized_keys") bash -s" <<'EOF'
set -euo pipefail

seed_keys_path="${SEED_KEYS}"
if [[ "${seed_keys_path}" != /* ]]; then
  seed_keys_path="${HOME}/${seed_keys_path#./}"
fi

if [[ ! -f "${seed_keys_path}" ]]; then
  echo "ERROR: seed authorized_keys file not found: ${seed_keys_path}" >&2
  exit 1
fi

sudo groupadd -f "${DEPLOY_USER}"

if ! id -u "${DEPLOY_USER}" >/dev/null 2>&1; then
  sudo useradd -m -g "${DEPLOY_USER}" -s /bin/bash "${DEPLOY_USER}"
fi

sudo usermod -g "${DEPLOY_USER}" -aG docker "${DEPLOY_USER}"

sudo install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
sudo install -m 600 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${seed_keys_path}" "/home/${DEPLOY_USER}/.ssh/authorized_keys"

sudo mkdir -p "${SHARED_DIR}"
sudo chown root:"${DEPLOY_USER}" "${SHARED_DIR}"
sudo chmod 2775 "${SHARED_DIR}"

if ! sudo test -d "${SHARED_DIR}/elasticsearch"; then
  sudo install -d -m 2775 -o root -g root "${SHARED_DIR}/elasticsearch"
fi
sudo chmod g+rwx "${SHARED_DIR}/elasticsearch"

echo
echo "Verification:"
id "${DEPLOY_USER}"
sudo ls -ld \
  "/home/${DEPLOY_USER}" \
  "/home/${DEPLOY_USER}/.ssh" \
  "/home/${DEPLOY_USER}/.ssh/authorized_keys" \
  "${SHARED_DIR}" \
  "${SHARED_DIR}/elasticsearch"
EOF

echo
echo "Bootstrap complete for ${host}."
echo "Next: verify SSH as ${deploy_user}@${host}, then set KAMAL_SSH_USER=${deploy_user} for that destination."
