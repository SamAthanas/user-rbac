import { useEffect } from 'preact/hooks';

export function Modal({ isOpen, onClose, title, children }) {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div style="
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 20px;
    ">
      <div style="
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        max-width: 600px;
        width: 100%;
        max-height: 90vh;
        overflow-y: auto;
      ">
        {/* Modal Header */}
        <div style="
          padding: 20px 20px 0 20px;
          border-bottom: 1px solid #e0e0e0;
          display: flex;
          justify-content: space-between;
          align-items: center;
        ">
          <h2 style="margin: 0; color: #1976d2; font-size: 18px;">
            {title}
          </h2>
          <button
            onClick={onClose}
            style="
              background: none;
              border: none;
              font-size: 24px;
              cursor: pointer;
              color: #666;
              padding: 0;
              width: 30px;
              height: 30px;
              display: flex;
              align-items: center;
              justify-content: center;
            "
          >
            ×
          </button>
        </div>

        {/* Modal Content */}
        <div style="padding: 20px;">
          {children}
        </div>
      </div>
    </div>
  );
}
