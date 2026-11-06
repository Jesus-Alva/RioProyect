"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import BranchMultiSelect from "./BranchMultiSelect.jsx";
import { OPERATIONAL_ROLES, ROLE_PROFILES } from "../lib/authRoles.js";
import { formatBranchNames } from "../lib/branches.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function statusLabel(status) {
  if (status === "active") return "Activo";
  if (status === "disabled") return "Deshabilitado";
  return "Pendiente";
}

export default function AdminUserManagement({ token, onUnauthorized }) {
  const reduceMotion = useReducedMotion();
  const [users, setUsers] = useState([]);
  const [selectedRoles, setSelectedRoles] = useState({});
  const [selectedBranches, setSelectedBranches] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [savingUserId, setSavingUserId] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadUsers(showLoading = false) {
    if (showLoading) setIsLoading(true);
    setError("");
    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/auth/admin/users`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (response.status === 401 || response.status === 403) {
        onUnauthorized();
        return;
      }
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo obtener la lista de usuarios.",
        );
      }
      setUsers(payload.users);
      setSelectedRoles(
        Object.fromEntries(
          payload.users.map((user) => [
            user.id,
            user.role || user.requested_role || "",
          ]),
        ),
      );
      setSelectedBranches(
        Object.fromEntries(
          payload.users.map((user) => [
            user.id,
              user.branches?.length
                ? user.branches
                : user.requested_branches || [],
          ]),
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "No se pudo conectar con el servicio de administración."
          : requestError.message,
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadUsers(true);
  }, [token]);

  const userCounts = users.reduce(
    (counts, user) => {
      counts[user.status] = (counts[user.status] || 0) + 1;
      return counts;
    },
    { pending: 0, active: 0, disabled: 0 },
  );
  const filteredUsers = users
    .filter((user) => {
      const matchesSearch = user.email
        .toLowerCase()
        .includes(searchQuery.trim().toLowerCase());
      const matchesStatus = statusFilter === "all" || user.status === statusFilter;
      const userRole = user.role || user.requested_role || "";
      const matchesRole = roleFilter === "all" || userRole === roleFilter;
      return matchesSearch && matchesStatus && matchesRole;
    })
    .sort((first, second) => {
      const statusPriority = { pending: 0, active: 1, disabled: 2 };
      return (
        (statusPriority[first.status] ?? 3) - (statusPriority[second.status] ?? 3) ||
        new Date(second.created_at || 0) - new Date(first.created_at || 0)
      );
    });

  function toggleUserAccess(user) {
    if (
      user.is_active &&
      !window.confirm(`¿Deshabilitar el acceso de ${user.email}?`)
    ) {
      return;
    }
    const changes = { is_active: !user.is_active };
    if (!user.is_active) {
      if (selectedBranches[user.id]?.length) {
        changes.branches = selectedBranches[user.id];
      }
      if (!user.role && selectedRoles[user.id]) changes.role = selectedRoles[user.id];
    }
    updateUser(user, changes);
  }

  async function updateUser(user, changes) {
    setSavingUserId(user.id);
    setError("");
    setNotice("");
    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/auth/admin/users/${user.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(changes),
        },
      );
      if (response.status === 401 || response.status === 403) {
        onUnauthorized();
        return;
      }
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo actualizar el acceso.",
        );
      }
      setNotice(`Permisos actualizados para ${user.email}.`);
      await loadUsers();
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "No se pudo conectar con el servicio de administración."
          : requestError.message,
      );
    } finally {
      setSavingUserId(null);
    }
  }

  return (
    <section
      className="role-dashboard admin-management"
      id="admin-users"
      aria-labelledby="admin-users-title"
    >
      <h2 id="admin-users-title">Usuarios y permisos</h2>
      <p>
        Aprueba solicitudes asignando rol y una o más sucursales. Las cuentas
        antiguas sin sucursal permanecen bloqueadas hasta una asignación explícita.
      </p>
      <div className="admin-user-summary" role="group" aria-label="Resumen de usuarios">
        <div className="admin-summary-card admin-summary-pending">
          <strong>{userCounts.pending}</strong>
          <span>Pendientes</span>
        </div>
        <div className="admin-summary-card">
          <strong>{userCounts.active}</strong>
          <span>Activos</span>
        </div>
        <div className="admin-summary-card">
          <strong>{userCounts.disabled}</strong>
          <span>Deshabilitados</span>
        </div>
      </div>
      <div className="admin-user-filters">
        <label className="admin-search-field">
          <span>Buscar por correo</span>
          <input
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="nombre@empresa.com"
          />
        </label>
        <label>
          <span>Estado</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">Todos</option>
            <option value="pending">Pendientes</option>
            <option value="active">Activos</option>
            <option value="disabled">Deshabilitados</option>
          </select>
        </label>
        <label>
          <span>Rol</span>
          <select
            value={roleFilter}
            onChange={(event) => setRoleFilter(event.target.value)}
          >
            <option value="all">Todos</option>
            {OPERATIONAL_ROLES.map((role) => (
              <option value={role} key={role}>
                {ROLE_PROFILES[role].label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {notice && (
        <p className="success-message" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {isLoading ? (
        <div className="admin-loading-state" role="status">Cargando usuarios…</div>
      ) : error ? (
        <div className="admin-error-state">
          <button
            className="button button-secondary"
            type="button"
            onClick={() => loadUsers(true)}
          >
            Reintentar
          </button>
        </div>
      ) : users.length === 0 ? (
        <div className="admin-empty-state">No hay cuentas registradas.</div>
      ) : (
        <div className="user-list">
          <AnimatePresence initial={false}>
            {filteredUsers.map((user, index) => {
              const isAdmin = user.role === "admin";
              const selectedRole = selectedRoles[user.id] || "";
              const isPending = user.status === "pending";
              const isDisabled = user.status === "disabled";
              return (
                <motion.article
                  className="user-card"
                  key={user.id}
                  layout
                  initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: reduceMotion ? 0 : -6 }}
                  transition={{
                    duration: reduceMotion ? 0 : 0.2,
                    delay: reduceMotion ? 0 : Math.min(index * 0.035, 0.2),
                  }}
                >
                  <div className="user-card-heading">
                    <strong>{user.username || user.email}</strong>
                    {user.username && <span>{user.email}</span>}
                    <span className={`user-status user-status-${user.status}`}>
                      {isAdmin ? "Administrador" : statusLabel(user.status)}
                    </span>
                  </div>
                  {isAdmin ? (
                    <p>Cuenta de administración; su rol no se modifica aquí.</p>
                  ) : (
                    <>
                      <div className="user-role-context">
                        <span>Rol solicitado</span>
                        <strong>
                          {user.requested_role
                            ? ROLE_PROFILES[user.requested_role]?.label || user.requested_role
                            : "—"}
                        </strong>
                        <span>Rol asignado</span>
                        <strong>
                          {user.role
                            ? ROLE_PROFILES[user.role]?.label || user.role
                            : "Sin asignar"}
                        </strong>
                        <span>Sucursal solicitada</span>
                        <strong>
                          {formatBranchNames(user.requested_branches)}
                        </strong>
                        <span>Sucursales asignadas</span>
                        <strong>{formatBranchNames(user.branches)}</strong>
                      </div>
                      <label htmlFor={`role-${user.id}`}>Rol operativo</label>
                      <select
                        id={`role-${user.id}`}
                        value={selectedRole}
                        onChange={(event) =>
                          setSelectedRoles((current) => ({
                            ...current,
                            [user.id]: event.target.value,
                          }))
                        }
                      >
                        <option value="" disabled>
                          Selecciona un rol
                        </option>
                        {OPERATIONAL_ROLES.map((role) => (
                          <option value={role} key={role}>
                            {ROLE_PROFILES[role].label}
                          </option>
                        ))}
                      </select>
                      <BranchMultiSelect
                        id={`branches-${user.id}`}
                        label="Sucursales autorizadas"
                        description="Selecciona una o más sucursales para esta cuenta."
                        selectedBranches={selectedBranches[user.id] || []}
                        onChange={(branches) =>
                          setSelectedBranches((current) => ({
                            ...current,
                            [user.id]: branches,
                          }))
                        }
                        disabled={savingUserId === user.id}
                      />
                      <div className="user-card-actions">
                        <button
                          className="button button-primary"
                          type="button"
                          disabled={
                            !selectedRole ||
                            !selectedBranches[user.id]?.length ||
                            savingUserId === user.id
                          }
                          onClick={() =>
                            updateUser(
                              user,
                              isPending || isDisabled
                                ? {
                                    role: selectedRole,
                                    branches: selectedBranches[user.id],
                                    is_active: true,
                                  }
                                : {
                                    role: selectedRole,
                                    branches: selectedBranches[user.id],
                                  },
                            )
                          }
                        >
                          {savingUserId === user.id
                            ? "Guardando..."
                            : isPending
                              ? "Asignar rol y aprobar"
                              : isDisabled
                                ? "Asignar rol y habilitar"
                                : "Guardar rol"}
                        </button>
                        {!isPending && (
                          <button
                            className="button button-secondary"
                            type="button"
                            disabled={
                              savingUserId === user.id ||
                              (!user.is_active &&
                                (!selectedBranches[user.id]?.length ||
                                  (!user.role && !selectedRole)))
                            }
                            onClick={() => toggleUserAccess(user)}
                          >
                            {user.is_active ? "Deshabilitar" : "Habilitar"}
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </motion.article>
              );
            })}
          </AnimatePresence>
          {filteredUsers.length === 0 && (
            <p className="admin-empty-state">No hay usuarios que coincidan con esos filtros.</p>
          )}
        </div>
      )}
    </section>
  );
}
