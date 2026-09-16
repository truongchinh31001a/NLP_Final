import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Providers } from "@/components/providers";
import "antd/dist/reset.css";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "LingoFlow Adaptive English",
  description: "Adaptive English learning workspace for tutoring and practice.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body className={`${inter.variable} bg-ae-page text-ae-ink antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
