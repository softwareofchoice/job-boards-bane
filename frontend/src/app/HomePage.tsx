import { Link } from "react-router-dom";

import { SUB_APPS } from "./subApps";

/** Describes each sub-app and links to it (FND-1.2). */
export function HomePage() {
  return (
    <section>
      <h1>Job Board&apos;s Bane</h1>
      <p className="lead">Tools for every step of the job search, running on your own machine.</p>
      <ul className="card-grid">
        {SUB_APPS.map((app) => (
          <li key={app.path} className="card">
            <h2>
              <Link to={app.path}>{app.name}</Link>
            </h2>
            <p>{app.summary}</p>
            {app.needsLlm ? <p className="card-note">Uses the local LLM.</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
