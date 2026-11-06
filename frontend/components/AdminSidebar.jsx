"use client";

import { useState } from "react";
import Image from "next/image";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

const NAV_ITEMS = [
  { id: "users", panelId: "admin-space-users", label: "Usuarios y permisos", icon: "users" },
  { id: "reviews", panelId: "admin-space-reviews", label: "Revisión de facturas", icon: "reviews" },
  { id: "agents", panelId: "admin-space-agents", label: "Agentes operativos", icon: "agents" },
];

export default function AdminSidebar({ activeSection, onSectionChange }) {
  const reduceMotion = useReducedMotion();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const duration = reduceMotion ? 0 : 0.24;

  return (
    <motion.aside
      className={`admin-sidebar ${isCollapsed ? "admin-sidebar-collapsed" : ""}`}
      animate={{ width: isCollapsed ? 72 : 248 }}
      transition={{ duration, ease: [0.22, 1, 0.36, 1] }}
      aria-label="Navegación del administrador"
    >
      <div className="admin-sidebar-heading">
        <span className="brand-logo-frame admin-sidebar-mark" aria-hidden="true">
          <Image
            src={isCollapsed ? "/rio-claro-icon.png" : "/rio-claro-logo.png"}
            alt=""
            fill
            sizes={isCollapsed ? "40px" : "112px"}
            className={`brand-logo-image ${isCollapsed ? "admin-sidebar-icon-image" : ""}`}
          />
        </span>
        <AnimatePresence initial={false}>
          {!isCollapsed && (
            <motion.span
              className="admin-sidebar-title"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration }}
            >
              Administración
            </motion.span>
          )}
        </AnimatePresence>
        <button
          className="admin-sidebar-toggle"
          type="button"
          onClick={() => setIsCollapsed((collapsed) => !collapsed)}
          aria-label={isCollapsed ? "Expandir menú" : "Contraer menú"}
          aria-expanded={!isCollapsed}
          aria-controls="admin-sidebar-navigation"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d={isCollapsed ? "m9 18 6-6-6-6" : "m15 18-6-6 6-6"} />
          </svg>
        </button>
      </div>

      <nav id="admin-sidebar-navigation" className="admin-sidebar-nav">
        <p className="admin-sidebar-caption">Espacios</p>
        {NAV_ITEMS.map((item) => (
          <button
            className={`admin-sidebar-link ${activeSection === item.id ? "is-active" : ""}`}
            type="button"
            key={item.id}
            aria-label={item.label}
            aria-current={activeSection === item.id ? "page" : undefined}
            aria-controls={item.panelId}
            title={isCollapsed ? item.label : undefined}
            onClick={() => onSectionChange(item.id)}
          >
            <AdminNavIcon kind={item.icon} />
            <AnimatePresence initial={false}>
              {!isCollapsed && (
                <motion.span
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -6 }}
                  transition={{ duration }}
                >
                  {item.label}
                </motion.span>
              )}
            </AnimatePresence>
          </button>
        ))}
      </nav>

      <div className="admin-sidebar-footer">
        <span className="admin-sidebar-live-dot" aria-hidden="true" />
        <AnimatePresence initial={false}>
          {!isCollapsed && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration }}
            >
              Sesión de administrador
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </motion.aside>
  );
}

function AdminNavIcon({ kind }) {
  return (
    <svg
      className="admin-sidebar-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {kind === "users" ? (
        <>
          <circle cx="9" cy="8" r="3" />
          <path d="M3.5 19v-1.5A4.5 4.5 0 0 1 8 13h2a4.5 4.5 0 0 1 4.5 4.5V19" />
          <path d="M16 5.5a3 3 0 0 1 0 5.8M17 13h.5a3 3 0 0 1 3 3V19" />
        </>
      ) : kind === "reviews" ? (
        <>
          <path d="M7 3.75h7l4 4V20a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5.75a2 2 0 0 1 2-2Z" />
          <path d="M14 4v4h4M8 12h7M8 16h7" />
        </>
      ) : (
        <>
          <path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />
          <path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" />
        </>
      )}
    </svg>
  );
}
