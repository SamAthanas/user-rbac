export function SuccessMessage({ message, onClose }) {
  return (
    <div class="success">
      <strong>Success:</strong> {message}
      <button onClick={onClose} style="float: right; background: none; border: none; color: #2e7d32; cursor: pointer;">×</button>
    </div>
  );
}
