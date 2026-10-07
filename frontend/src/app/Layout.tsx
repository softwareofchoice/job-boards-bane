import { NavLink, Outlet } from "react-router-dom";

import { HealthBadge } from "../components/HealthBadge";
import { SUB_APPS } from "./subApps";

const SHORT_NAMES: Record<string, string> = {
  "/tracker": "Tracker",
  "/scraper": "Job Scraper",
  "/resume-rounder": "Resume Rounder",
};

export function Layout() {
  return (
    <>
      <header className="app-header">
        <nav aria-label="Main">
          <NavLink to="/" end className="brand">
            Job Board&apos;s Bane
          </NavLink>
          <NavLink to="/" end>
            Home
          </NavLink>
          {SUB_APPS.map((app) => (
            <NavLink key={app.path} to={app.path}>
              {SHORT_NAMES[app.path] ?? app.name}
            </NavLink>
          ))}
        </nav>
        <HealthBadge />
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </>
  );
}
