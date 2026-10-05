import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { Report } from "./components/Report";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {location.pathname.replace(/\/$/, "") === "/report" ? <Report /> : <App />}
  </StrictMode>,
);
