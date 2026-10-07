import { Route, Routes } from "react-router-dom";

import { ApplicationDetailPage } from "./ApplicationDetailPage";
import { ApplicationListPage } from "./ApplicationListPage";
import { NewApplicationPage } from "./NewApplicationPage";

/** Job Application Tracker: `/tracker`, `/tracker/new`, `/tracker/:id`. */
export default function TrackerPage() {
  return (
    <Routes>
      <Route index element={<ApplicationListPage />} />
      <Route path="new" element={<NewApplicationPage />} />
      <Route path=":id" element={<ApplicationDetailPage />} />
    </Routes>
  );
}
