import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Enterprise Unified Platform | $104M+ Integration Hub',
  description: 'Unprecedented enterprise-grade platform with real-time analytics across 60+ integrated systems. Built for multi-million dollar conference presentations.',
  keywords: ['enterprise', 'platform', 'integration', 'analytics', 'dashboard', 'hubspot'],
  authors: [{ name: 'Garrett Carrol' }],
  openGraph: {
    title: 'Enterprise Unified Platform',
    description: '$104M+ Revenue Potential | 60+ Integrated Systems',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
