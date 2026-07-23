import { NavLink, Outlet } from "react-router-dom";

const navigation = [
  ["/", "Home"],
  ["/runs", "Runs"],
  ["/scenarios", "Scenarios"],
  ["/comparisons", "Comparisons"],
  ["/universes", "Universes"],
  ["/detectors", "Detector Lab"],
  ["/motifs", "Motifs"],
  ["/policies", "Policies"],
  ["/artifacts", "Artifacts"],
  ["/capabilities", "Capabilities"],
] as const;

export function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">PG</span>
          <div>
            <strong>PlanGuard</strong>
            <span>Performance Workbench</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          {navigation.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="milestone-note">
          <span className="status-dot supported" />
          Milestone F
          <small>Universe coverage & corpus evolution</small>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
