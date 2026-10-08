import { Route, Routes } from "react-router-dom";

import { LlmWarning } from "../../components/LlmWarning";
import { RunPage } from "./RunPage";
import { SearchPage } from "./SearchPage";

/** Web Job Scraper: `/scraper` (search + past runs) and `/scraper/runs/:id`. */
export default function ScraperPage() {
  return (
    <>
      <LlmWarning />
      <Routes>
        <Route index element={<SearchPage />} />
        <Route path="runs/:id" element={<RunPage />} />
      </Routes>
    </>
  );
}
