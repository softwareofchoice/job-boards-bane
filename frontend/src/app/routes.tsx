/* eslint-disable react-refresh/only-export-components -- route config, not a component module */
import { lazy, Suspense, type ReactNode } from "react";
import type { RouteObject } from "react-router-dom";

import { HomePage } from "./HomePage";
import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";

// Each sub-app is its own bundle, loaded when first visited.
const TrackerPage = lazy(() => import("../features/tracker/TrackerPage"));
const ScraperPage = lazy(() => import("../features/scraper/ScraperPage"));
const RounderPage = lazy(() => import("../features/rounder/RounderPage"));

function page(element: ReactNode) {
  return <Suspense fallback={<p aria-busy="true">Loading…</p>}>{element}</Suspense>;
}

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "tracker/*", element: page(<TrackerPage />) },
      { path: "scraper/*", element: page(<ScraperPage />) },
      { path: "resume-rounder/*", element: page(<RounderPage />) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
