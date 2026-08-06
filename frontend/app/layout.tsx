import type { Metadata } from "next";
import { TopNav } from "@/components/TopNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Argus — Real-Time Fraud Detection Engine",
  description:
    "Synthetic transaction stream, causal feature engineering, an XGBoost + Isolation Forest ensemble, and SHAP explainability — scored live.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TopNav />
        <main className="container" style={{ paddingTop: 24 }}>
          {children}
        </main>
      </body>
    </html>
  );
}
