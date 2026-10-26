import React, { useEffect, useState, useRef } from "react";

interface PageTransitionProps {
  pageKey: string;
  children: React.ReactNode;
}

/**
 * Wraps page content with a fade-in-up animation whenever the pageKey changes.
 * Uses a simple CSS class swap to trigger the animation without adding
 * a heavy animation library.
 */
export const PageTransition: React.FC<PageTransitionProps> = ({ pageKey, children }) => {
  const [currentKey, setCurrentKey] = useState(pageKey);
  const [animating, setAnimating] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pageKey !== currentKey) {
      setAnimating(false);
      // Short delay to allow old content to fade then swap
      const timeout = setTimeout(() => {
        setCurrentKey(pageKey);
        setAnimating(true);
      }, 80);
      return () => clearTimeout(timeout);
    }
  }, [pageKey, currentKey]);

  return (
    <div
      ref={containerRef}
      className={animating ? "page-transition-enter" : ""}
      style={{
        opacity: animating ? 1 : 0,
        transition: "opacity 80ms ease",
        flex: 1,
      }}
    >
      {children}
    </div>
  );
};
