type AnyJson = Record<string, unknown>;

function isString(x: unknown): x is string {
  return typeof x === "string";
}

function getInfoId(info: AnyJson): string | null {
  const id = info.id ?? info["@id"];
  return isString(id) ? id : null;
}

function getInfoDims(info: AnyJson): { width: number | null; height: number | null } {
  const w = info.width;
  const h = info.height;
  return {
    width: typeof w === "number" ? w : null,
    height: typeof h === "number" ? h : null,
  };
}

function inferImageUrl(serviceId: string): string {
  // Prefer Image API 3 style; many Image API 2 servers accept it too.
  return `${serviceId.replace(/\/$/, "")}/full/max/0/default.jpg`;
}

/**
 * Build a minimal IIIF Presentation 3 manifest for an IIIF Image Service.
 * This lets Mirador render `iiif_image` references by converting them into a manifest.
 */
export function buildPresentation3ManifestFromImageInfo(args: {
  manifestId: string;
  imageServiceId: string;
  info: AnyJson;
}): AnyJson {
  const { manifestId, imageServiceId, info } = args;
  const { width, height } = getInfoDims(info);

  const canvasId = `${manifestId}#canvas-1`;
  const pageId = `${manifestId}#page-1`;
  const annotationId = `${manifestId}#annotation-1`;

  return {
    "@context": "http://iiif.io/api/presentation/3/context.json",
    id: manifestId,
    type: "Manifest",
    label: { en: ["Image"] },
    items: [
      {
        id: canvasId,
        type: "Canvas",
        ...(width ? { width } : {}),
        ...(height ? { height } : {}),
        items: [
          {
            id: pageId,
            type: "AnnotationPage",
            items: [
              {
                id: annotationId,
                type: "Annotation",
                motivation: "painting",
                target: canvasId,
                body: {
                  id: inferImageUrl(imageServiceId),
                  type: "Image",
                  format: "image/jpeg",
                  service: [
                    {
                      id: imageServiceId,
                      type: "ImageService3",
                    },
                  ],
                },
              },
            ],
          },
        ],
      },
    ],
  };
}

export async function fetchIiifImageInfo(imageServiceOrInfoUrl: string): Promise<AnyJson> {
  const base = imageServiceOrInfoUrl.replace(/\/$/, "");
  const infoUrl = base.endsWith("/info.json") ? base : `${base}/info.json`;

  const resp = await fetch(infoUrl, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!resp.ok) {
    throw new Response(`Failed to fetch IIIF info.json: ${resp.status}`, {
      status: resp.status,
    });
  }

  return (await resp.json()) as AnyJson;
}

export function normalizeImageServiceId(imageServiceOrInfoUrl: string, info: AnyJson): string {
  // Prefer canonical id from info.json when available.
  const canonical = getInfoId(info);
  if (canonical) return canonical.replace(/\/info\.json$/, "").replace(/\/$/, "");
  return imageServiceOrInfoUrl.replace(/\/info\.json$/, "").replace(/\/$/, "");
}

