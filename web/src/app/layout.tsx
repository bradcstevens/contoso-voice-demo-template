import './globals.css'
import type { Metadata } from "next";
import { version } from '@/store/version';
import styles from './layout.module.css';



export const metadata: Metadata = {
  title: "DigiKey",
  description:
    "AI-powered electronics component recommendations and expert product assistance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        
        {children}
        
        <div className={styles.version}>{version}</div>
      </body>
    </html>
  );
}
