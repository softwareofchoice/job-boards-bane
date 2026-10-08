import { Route, Routes } from "react-router-dom";

import { LlmWarning } from "../../components/LlmWarning";
import { GeneratePage } from "./GeneratePage";
import { GenerationPage } from "./GenerationPage";
import { SkillsPage } from "./SkillsPage";

/** Resume Rounder: `/resume-rounder`, `/resume-rounder/skills`, `/resume-rounder/generations/:id`. */
export default function RounderPage() {
  return (
    <>
      <LlmWarning />
      <Routes>
        <Route index element={<GeneratePage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="generations/:id" element={<GenerationPage />} />
      </Routes>
    </>
  );
}
