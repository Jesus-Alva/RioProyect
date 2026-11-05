import "./globals.css";

export const metadata = {
  title: "Asistente Río Claro",
  description: "Asistente de IA para Distribuidora Río Claro.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es-MX">
      <body>{children}</body>
    </html>
  );
}
