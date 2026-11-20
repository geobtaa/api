import { useState } from 'react';
import { Link, useBeforeUnload, useBlocker, useParams } from 'react-router';
import { Load } from '../sources/SourceBrowse';
import { DiscardDialog } from '../ui/DiscardDialog';
import { ui } from '../ui/styles';
import { decodeId, encodeId } from '../urlIds';
import { WorkflowPanel } from '../workflows/WorkflowPanel';
import { setBase, type SetRecord } from './api';

export function SetWorkflowsPage() {
  const { setId } = useParams();
  const id = decodeId(setId ?? '');
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to={`/sets/${encodeId(id)}`}>
        Back to Set
      </Link>
      <Load<SetRecord> url={`${setBase}/${encodeURIComponent(id)}`}>
        {(item) => <Editor item={item} />}
      </Load>
    </main>
  );
}

function Editor({ item }: { item: SetRecord }) {
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const blocker = useBlocker(busy || dirty);
  useBeforeUnload((event) => {
    if (busy || dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  return (
    <>
      <h1>Workflows for {item.title}</h1>
      <WorkflowPanel
        setId={item.set_id}
        retired={item.status === 'retired'}
        disabled={false}
        onBusy={setBusy}
        onDirty={setDirty}
        onChanged={() => setDirty(false)}
      />
      {blocker.state === 'blocked' && (
        <DiscardDialog
          busy={busy}
          keep={() => blocker.reset()}
          discard={() => blocker.proceed()}
        />
      )}
    </>
  );
}
