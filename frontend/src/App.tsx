import React, { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { ToastProvider } from "./components/Toast";
import { PageTransition } from "./components/PageTransition";
import { OverviewPage } from "./pages/OverviewPage";
import { DatasetsPage } from "./pages/DatasetsPage";
import { QueriesPage } from "./pages/QueriesPage";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { ResultsPage } from "./pages/ResultsPage";
import { TestsPage } from "./pages/TestsPage";
import { SystemPage } from "./pages/SystemPage";

export const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<string>("overview");
  const [selectedExpId, setSelectedExpId] = useState<string>("");

  const handleNavigate = (pageTarget: string) => {
    if (pageTarget.startsWith("results:")) {
      const expId = pageTarget.replace("results:", "");
      setSelectedExpId(expId);
      setCurrentPage("results");
    } else {
      setCurrentPage(pageTarget);
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Keyboard navigation shortcuts: 1-7 navigates between pages
  // Only triggers when the user is NOT typing in an input/textarea/select
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement;
      const isInput =
        activeEl?.tagName === "INPUT" ||
        activeEl?.tagName === "TEXTAREA" ||
        activeEl?.tagName === "SELECT";

      if (isInput) return;

      const pageMap: Record<string, string> = {
        "1": "overview",
        "2": "datasets",
        "3": "queries",
        "4": "benchmark",
        "5": "results",
        "6": "tests",
        "7": "system",
      };

      if (pageMap[e.key]) {
        e.preventDefault();
        handleNavigate(pageMap[e.key]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <ToastProvider>
      <div className="app-container">
        <a href="#main-content" className="skip-to-content">
          Chuyển đến nội dung chính
        </a>
        <div className="main-content" id="main-content">
          <Navbar currentPage={currentPage} onNavigate={handleNavigate} />
          <PageTransition pageKey={currentPage}>
            {currentPage === "overview" && <OverviewPage onNavigate={handleNavigate} />}
            {currentPage === "datasets" && <DatasetsPage />}
            {currentPage === "queries" && <QueriesPage />}
            {currentPage === "benchmark" && <BenchmarkPage onNavigate={handleNavigate} />}
            {currentPage === "results" && <ResultsPage initialExpId={selectedExpId} />}
            {currentPage === "tests" && <TestsPage />}
            {currentPage === "system" && <SystemPage />}
          </PageTransition>
        </div>
      </div>
    </ToastProvider>
  );
};
