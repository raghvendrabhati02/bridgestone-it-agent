import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bridgestone IT Agent – Service Portal",
  description:
    "Enterprise IT Service Management portal powered by AI. Submit tickets, manage approvals, monitor system health, and resolve IT issues with conversational AI support.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="h-full bg-[#0f1117] text-slate-100">{children}</body>
    </html>
  );
}
