import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Neurocache Dashboard",
  description: "AI-Native Semantic Cache and Multi-Provider Cost Router",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased`}>
        <div className="min-h-screen bg-background text-foreground flex flex-col">
          {/* Top Navigation */}
          <header className="h-16 border-b border-cardBorder flex items-center px-6 sticky top-0 z-50 bg-background/80 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center text-black font-bold">
                N
              </div>
              <h1 className="text-xl font-bold tracking-tight">Neurocache</h1>
            </div>
          </header>
          
          <main className="flex-1 p-6 lg:p-8 max-w-7xl mx-auto w-full">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
