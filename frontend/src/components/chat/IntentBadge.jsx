import Badge from '../common/Badge';

export default function IntentBadge({ intent, confidence, confidenceLabel }) {
  const confVariant = confidence >= 0.8 ? 'confidence-high' : confidence >= 0.5 ? 'confidence-mid' : 'confidence-low';

  return (
    <div className="flex gap-1.5 mb-2 flex-wrap">
      <Badge variant="intent">{intent}</Badge>
      {confidence != null && (
        <Badge variant={confVariant}>confidence {confidence} · {confidenceLabel}</Badge>
      )}
    </div>
  );
}
