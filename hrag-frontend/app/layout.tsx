import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: [
    { path: "../public/Geist/Geist-Thin.ttf", weight: "100" },
    { path: "../public/Geist/Geist-ExtraLight.ttf", weight: "200" },
    { path: "../public/Geist/Geist-Light.ttf", weight: "300" },
    { path: "../public/Geist/Geist-Regular.ttf", weight: "400" },
    { path: "../public/Geist/Geist-Medium.ttf", weight: "500" },
    { path: "../public/Geist/Geist-SemiBold.ttf", weight: "600" },
    { path: "../public/Geist/Geist-Bold.ttf", weight: "700" },
    { path: "../public/Geist/Geist-ExtraBold.ttf", weight: "800" },
    { path: "../public/Geist/Geist-Black.ttf", weight: "900" },
  ],
  variable: "--font-geist-sans",
});

const geistMono = localFont({
  src: [
    { path: "../public/Geist_Mono/GeistMono-Thin.ttf", weight: "100" },
    { path: "../public/Geist_Mono/GeistMono-ExtraLight.ttf", weight: "200" },
    { path: "../public/Geist_Mono/GeistMono-Light.ttf", weight: "300" },
    { path: "../public/Geist_Mono/GeistMono-Regular.ttf", weight: "400" },
    { path: "../public/Geist_Mono/GeistMono-Medium.ttf", weight: "500" },
    { path: "../public/Geist_Mono/GeistMono-SemiBold.ttf", weight: "600" },
    { path: "../public/Geist_Mono/GeistMono-Bold.ttf", weight: "700" },
    { path: "../public/Geist_Mono/GeistMono-ExtraBold.ttf", weight: "800" },
    { path: "../public/Geist_Mono/GeistMono-Black.ttf", weight: "900" },
  ],
  variable: "--font-geist-mono",
});

export const metadata: Metadata = {
  title: "HRAG - Hybrid RAG System",
  description: "Hybrid Retrieval-Augmented Generation for DevOps Incident Response",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-black text-slate-200`}
      >
        {children}
      </body>
    </html>
  );
}
