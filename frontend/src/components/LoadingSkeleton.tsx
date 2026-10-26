import React from "react";

interface LoadingSkeletonProps {
  width?: string;
  height?: string;
  variant?: "text" | "card" | "table-row" | "circle";
  count?: number;
  className?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  width,
  height,
  variant = "text",
  count = 1,
  className = "",
}) => {
  const getVariantClass = () => {
    switch (variant) {
      case "card":
        return "skeleton skeleton-card";
      case "table-row":
        return "skeleton skeleton-table-row";
      case "circle":
        return "skeleton skeleton-circle";
      default:
        return "skeleton skeleton-text";
    }
  };

  const items = Array.from({ length: count }, (_, i) => (
    <div
      key={i}
      className={`${getVariantClass()} ${className}`}
      style={{
        width: width || (variant === "circle" ? "40px" : "100%"),
        height:
          height ||
          (variant === "card"
            ? "120px"
            : variant === "table-row"
            ? "48px"
            : variant === "circle"
            ? "40px"
            : "14px"),
      }}
    />
  ));

  return <>{items}</>;
};

/** Skeleton wrapper for a full card loading state */
export const CardSkeleton: React.FC = () => (
  <div className="card" style={{ padding: "1.5rem" }}>
    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.25rem" }}>
      <LoadingSkeleton variant="circle" width="32px" height="32px" />
      <LoadingSkeleton width="40%" height="18px" />
    </div>
    <LoadingSkeleton count={3} />
    <div style={{ marginTop: "0.5rem" }}>
      <LoadingSkeleton width="70%" />
    </div>
  </div>
);

/** Skeleton wrapper for a table loading state */
export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => (
  <div className="table-wrapper" style={{ padding: "0.5rem" }}>
    <LoadingSkeleton variant="table-row" height="40px" />
    <LoadingSkeleton variant="table-row" count={rows} />
  </div>
);
