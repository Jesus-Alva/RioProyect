import "./globals.css";

export const metadata = {
  title: "Asistente Río Claro",
  description: "Asistente de IA para Distribuidora Río Claro.",
  icons: {
    icon: "/rio-claro-icon.png",
    apple: "/rio-claro-icon.png",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="es-MX">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
