import React, { useEffect, useState } from "react";
import {
  Database,
  Activity,
  Layers,
  PlayCircle,
  BarChart3,
  CheckCircle2,
  Server,
} from "lucide-react";
import { fetchHealth, SystemHealth } from "../api";
import { ThemeToggle } from "./ThemeToggle";

interface NavbarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentPage, onNavigate }) => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        const data = await fetchHealth();
        setHealth(data);
      } catch (err) {
        // DB offline or backend unreachable
      }
    };
    check();
    const interval = setInterval(check, 5000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: "overview", label: "Tổng quan", icon: Activity, key: "1" },
    { id: "datasets", label: "Dữ liệu", icon: Database, key: "2" },
    { id: "queries", label: "Truy vấn", icon: Layers, key: "3" },
    { id: "benchmark", label: "Benchmark", icon: PlayCircle, key: "4" },
    { id: "results", label: "Kết quả", icon: BarChart3, key: "5" },
    { id: "tests", label: "Kiểm thử", icon: CheckCircle2, key: "6" },
    { id: "system", label: "Hệ thống", icon: Server, key: "7" },
  ];

  const pgHealthy = !!health?.engines?.postgresql?.is_healthy;
  const mongoHealthy = !!health?.engines?.mongodb?.is_healthy;
  const pgLatency = health?.engines?.postgresql?.latency_ms?.toFixed(1);
  const mongoLatency = health?.engines?.mongodb?.latency_ms?.toFixed(1);

  const handleItemClick = (id: string) => {
    onNavigate(id);
    setMobileMenuOpen(false);
  };

  return (
    <>
      <nav className="top-navbar" role="navigation" aria-label="Main Navigation">
        {/* Brand */}
        <div className="brand-section">
          <div className="brand-logo" title="PT Lab Platform">
            <img src="/logo.png" alt="PT Lab Logo" className="brand-logo-img" />
          </div>
          <div>
            <span className="brand-title">PT Lab</span>
            <span className="brand-badge" style={{ marginLeft: "8px" }}>
              v2.0
            </span>
          </div>
        </div>

        {/* Desktop Navigation Links */}
        <div className="nav-links">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                className={`nav-btn ${isActive ? "active" : ""}`}
                onClick={() => handleItemClick(item.id)}
                title={`Nhấn phím ${item.key} để mở`}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon size={16} />
                <span>{item.label}</span>
                <span
                  style={{
                    fontSize: "0.65rem",
                    opacity: 0.5,
                    marginLeft: "2px",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  [{item.key}]
                </span>
              </button>
            );
          })}
        </div>

        {/* Right Status + Controls */}
        <div className="header-status">
          <div
            className="engine-pill pg"
            title={
              pgHealthy
                ? `PostgreSQL 17.2: Online (${pgLatency}ms)`
                : "PostgreSQL 17.2: Offline"
            }
          >
            <span className={`pulse-dot ${pgHealthy ? "online" : "offline"}`} />
            <span>PostgreSQL 17.2 {pgHealthy && `(${pgLatency}ms)`}</span>
          </div>

          <div
            className="engine-pill mongo"
            title={
              mongoHealthy
                ? `MongoDB 8.0.4: Online (${mongoLatency}ms)`
                : "MongoDB 8.0.4: Offline"
            }
          >
            <span className={`pulse-dot ${mongoHealthy ? "online" : "offline"}`} />
            <span>MongoDB 8.0 {mongoHealthy && `(${mongoLatency}ms)`}</span>
          </div>

          <ThemeToggle />

          {/* Hamburger button for mobile */}
          <button
            className={`hamburger-btn ${mobileMenuOpen ? "open" : ""}`}
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </nav>

      {/* Mobile Navigation Dropdown */}
      <div
        className={`mobile-nav-dropdown ${mobileMenuOpen ? "open" : ""}`}
        role="menu"
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              className={`nav-btn ${isActive ? "active" : ""}`}
              onClick={() => handleItemClick(item.id)}
              style={{ width: "100%", justifyContent: "flex-start" }}
              role="menuitem"
            >
              <Icon size={16} />
              <span>{item.label}</span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: "0.7rem",
                  opacity: 0.5,
                  fontFamily: "var(--font-mono)",
                }}
              >
                [{item.key}]
              </span>
            </button>
          );
        })}
      </div>
    </>
  );
};
