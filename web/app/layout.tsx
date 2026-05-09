import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Electrical Compliance Agent",
  description:
    "CrewAI + Supabase RAG demo for electrical compliance review and material support.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
