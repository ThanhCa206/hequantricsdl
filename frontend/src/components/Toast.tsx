import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import ReactDOM from "react-dom";
import { CheckCircle2, AlertTriangle, Info, XCircle, X } from "lucide-react";

export type ToastType = "success" | "error" | "warning" | "info";

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration: number;
  exiting?: boolean;
}

interface ToastContextValue {
  addToast: (type: ToastType, message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue>({
  addToast: () => {},
});

export const useToast = () => useContext(ToastContext);

const ToastIcon: React.FC<{ type: ToastType }> = ({ type }) => {
  const iconProps = { size: 20, className: "toast-icon" };
  switch (type) {
    case "success":
      return <CheckCircle2 {...iconProps} color="var(--success)" />;
    case "error":
      return <XCircle {...iconProps} color="var(--danger)" />;
    case "warning":
      return <AlertTriangle {...iconProps} color="var(--warning)" />;
    case "info":
      return <Info {...iconProps} color="var(--pg-color)" />;
  }
};

const ToastComponent: React.FC<{
  toast: ToastItem;
  onDismiss: (id: string) => void;
}> = ({ toast, onDismiss }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, toast.duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div className={`toast toast-${toast.type} ${toast.exiting ? "exiting" : ""}`}>
      <ToastIcon type={toast.type} />
      <span className="toast-message">{toast.message}</span>
      <button className="toast-close" onClick={() => onDismiss(toast.id)} aria-label="Đóng thông báo">
        <X size={16} />
      </button>
    </div>
  );
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((type: ToastType, message: string, duration: number = 4000) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { id, type, message, duration }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    // Mark as exiting first for animation
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, exiting: true } : t))
    );
    // Remove after animation completes
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 250);
  }, []);

  const portalContent = toasts.length > 0 ? (
    <div className="toast-container">
      {toasts.map((toast) => (
        <ToastComponent key={toast.id} toast={toast} onDismiss={dismissToast} />
      ))}
    </div>
  ) : null;

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      {portalContent && ReactDOM.createPortal(portalContent, document.body)}
    </ToastContext.Provider>
  );
};
