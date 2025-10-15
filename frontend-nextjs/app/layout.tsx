import "./globals.css";

export const metadata = {
  title: "Multi-Agent Workshop",
  description: "Next.js UI (secondary)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
