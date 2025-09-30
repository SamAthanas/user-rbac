export function ErrorMessage({ message, onClose }) {
  return (
    <div class="error">
      <strong>Error:</strong> {message}
      <button onClick={onClose} style="float: right; background: none; border: none; color: #c62828; cursor: pointer;">×</button>
    </div>
  );
}
