import {
  type FormEvent,
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import * as api from "./api";
import type {
  AdminAccount,
  AdminStats,
  AdminUser,
  AppSettings,
  Car,
  CarImage,
  Lead,
  LeadStatus,
  LeadType,
  Trim,
} from "./types";

interface AuthState {
  admin: AdminUser | null;
  setAdmin: (admin: AdminUser | null) => void;
}

const AuthContext = createContext<AuthState | null>(null);
const ToastContext = createContext<(text: string, isError?: boolean) => void>(() => undefined);
const STATUS_LABELS: Record<LeadStatus, string> = {
  new: "Yangi",
  accepted: "Qabul qilindi",
  contacted: "Bog'lanildi",
  cancelled: "Bekor qilindi",
  done: "Yakunlandi",
};
const TYPE_LABELS: Record<LeadType, string> = {
  test_drive: "Test-drayv",
  buy: "Sotib olish",
  callback: "Qayta qo'ng'iroq",
};

function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("AuthContext mavjud emas");
  return auth;
}

function useToast() {
  return useContext(ToastContext);
}

function App() {
  const [admin, setAdmin] = useState<AdminUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [toast, setToast] = useState<{ text: string; isError: boolean } | null>(null);

  useEffect(() => {
    api.getAdmin()
      .then(setAdmin)
      .catch(() => setAdmin(null))
      .finally(() => setChecking(false));
  }, []);

  const notify = (text: string, isError = false) => {
    setToast({ text, isError });
    window.setTimeout(() => setToast(null), 3600);
  };

  if (checking) return <div className="full-loader">Yuklanmoqda…</div>;

  return (
    <AuthContext.Provider value={{ admin, setAdmin }}>
      <ToastContext.Provider value={notify}>
        <Routes>
          <Route path="/login" element={admin ? <Navigate to="/" replace /> : <LoginPage />} />
          <Route path="/*" element={admin ? <AdminShell /> : <Navigate to="/login" replace />} />
        </Routes>
        {toast && (
          <div className={`toast ${toast.isError ? "toast-error" : ""}`} role="status">
            {toast.text}
          </div>
        )}
      </ToastContext.Provider>
    </AuthContext.Provider>
  );
}

function LoginPage() {
  const { setAdmin } = useAuth();
  const notify = useToast();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorText, setErrorText] = useState("");
  const loginMutation = useMutation({
    mutationFn: () => api.login(username.trim(), password),
    onSuccess: (user) => {
      setAdmin(user);
      navigate("/", { replace: true });
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : "Kirish amalga oshmadi.";
      setErrorText(message);
      notify(message, true);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorText("");
    loginMutation.mutate();
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="brand-mark">BAM</div>
        <p className="eyebrow">BUXARA AVTO MAGNAT · VOLKSWAGEN</p>
        <h1>Admin panel</h1>
        <p className="muted">Davom etish uchun hisobingizga kiring.</p>
        <label>
          Foydalanuvchi nomi
          <input
            autoComplete="username"
            autoFocus
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label>
          Parol
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {errorText && <p className="form-error" role="alert">{errorText}</p>}
        <button className="button button-primary button-wide" disabled={loginMutation.isPending}>
          {loginMutation.isPending ? "Tekshirilmoqda…" : "Kirish"}
        </button>
      </form>
    </main>
  );
}

const NAV_ITEMS: { to: string; label: string; owner?: boolean }[] = [
  { to: "/", label: "Boshqaruv paneli" },
  { to: "/leads", label: "Arizalar" },
  { to: "/cars", label: "Avtomobillar" },
  { to: "/users", label: "Foydalanuvchilar" },
  { to: "/broadcast", label: "Xabar yuborish" },
  { to: "/settings", label: "Sozlamalar", owner: true },
  { to: "/audit", label: "Audit jurnali", owner: true },
  { to: "/accounts", label: "Admin hisoblari", owner: true },
];

function AdminShell() {
  const { admin, setAdmin } = useAuth();
  const notify = useToast();
  const navigate = useNavigate();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      setAdmin(null);
      navigate("/login", { replace: true });
    },
    onError: (error) => notify(error.message, true),
  });

  if (!admin) return <Navigate to="/login" replace />;
  const visibleItems = NAV_ITEMS.filter((item) => !item.owner || admin.role === "owner");

  return (
    <div className="admin-layout">
      <aside className={`sidebar ${mobileNavOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark brand-mark-small">BAM</div>
          <div>
            <strong>Buxara Avto Magnat</strong>
            <span>Volkswagen · Admin</span>
          </div>
        </div>
        <nav aria-label="Asosiy navigatsiya">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              end={item.to === "/"}
              to={item.to}
              onClick={() => setMobileNavOpen(false)}
              className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="admin-identity">
            <span className="avatar">{admin.username.slice(0, 1).toUpperCase()}</span>
            <span><strong>{admin.username}</strong><small>{admin.role === "owner" ? "Owner" : "Manager"}</small></span>
          </div>
          <button className="button button-quiet button-wide" onClick={() => logoutMutation.mutate()}>
            Chiqish
          </button>
        </div>
      </aside>
      <div className="admin-main">
        <header className="topbar">
          <button
            className="mobile-menu button button-quiet"
            aria-label="Navigatsiyani ochish"
            onClick={() => setMobileNavOpen((open) => !open)}
          >
            Menyu
          </button>
          <span className="topbar-caption">Boshqaruv</span>
          <span className="topbar-role">{admin.role === "owner" ? "Owner" : "Manager"}</span>
        </header>
        <main className="page-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/leads" element={<LeadsPage />} />
            <Route path="/cars" element={<CarsPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/broadcast" element={<BroadcastPage />} />
            <Route path="/settings" element={admin.role === "owner" ? <SettingsPage /> : <ForbiddenPage />} />
            <Route path="/audit" element={admin.role === "owner" ? <AuditPage /> : <ForbiddenPage />} />
            <Route path="/accounts" element={admin.role === "owner" ? <AccountsPage /> : <ForbiddenPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">BUXARA AVTO MAGNAT</p>
        <h1>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

function LoadingState({ label = "Ma'lumotlar yuklanmoqda…" }: { label?: string }) {
  return <div className="state-card" role="status"><span className="spinner" />{label}</div>;
}

function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const text = error instanceof Error ? error.message : "Ma'lumotlarni yuklab bo'lmadi.";
  return (
    <div className="state-card state-error" role="alert">
      <strong>So'rov bajarilmadi</strong>
      <span>{text}</span>
      {retry && <button className="button button-secondary" onClick={retry}>Qayta urinish</button>}
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("uz-UZ", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function DashboardPage() {
  const statsQuery = useQuery({ queryKey: ["admin-stats"], queryFn: api.getStats });
  const leadsQuery = useQuery({
    queryKey: ["admin-latest-leads"],
    queryFn: () => api.getLeads(new URLSearchParams({ limit: "10", offset: "0" })),
  });

  return (
    <section>
      <PageHeader title="Boshqaruv paneli" description="Dilerlik faoliyatining qisqa ko'rinishi." />
      {statsQuery.isPending ? <LoadingState /> : statsQuery.isError ? (
        <ErrorState error={statsQuery.error} retry={() => void statsQuery.refetch()} />
      ) : <DashboardContent stats={statsQuery.data} />}
      <div className="section-heading">
        <h2>So'nggi arizalar</h2>
        <Link className="text-link" to="/leads">Barchasini ko'rish</Link>
      </div>
      {leadsQuery.isPending ? <LoadingState /> : leadsQuery.isError ? (
        <ErrorState error={leadsQuery.error} retry={() => void leadsQuery.refetch()} />
      ) : <LeadTable leads={leadsQuery.data.items} compact />}
    </section>
  );
}

function DashboardContent({ stats }: { stats: AdminStats }) {
  const statusEntries = Object.entries(stats.leads_by_status);
  const maxDaily = Math.max(1, ...stats.daily_leads_30d.map((day) => day.count));
  return (
    <>
      <div className="kpi-grid">
        <KpiCard label="Bugungi yangi arizalar" value={stats.leads_today} />
        <KpiCard label="So'nggi 7 kun" value={stats.leads_week} />
        <KpiCard label="Foydalanuvchilar jami" value={stats.users_total} detail={`So'nggi 30 kunda +${stats.users_new_30d}`} />
        <KpiCard label="Arizalar jami" value={stats.leads_total} detail={`Yakunlangan: ${stats.conversion_new_to_done_percent.toFixed(1)}%`} />
      </div>
      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="panel-heading"><h2>Oxirgi 30 kun</h2><span className="muted">Kunlik arizalar</span></div>
          <div className="bar-chart" role="img" aria-label="Oxirgi 30 kundagi kunlik arizalar diagrammasi">
            {stats.daily_leads_30d.map((day) => (
              <div className="bar-column" key={day.date} title={`${day.date}: ${day.count}`}>
                <span className="bar-value">{day.count || ""}</span>
                <span className="bar" style={{ height: `${Math.max(3, (day.count / maxDaily) * 100)}%` }} />
                <span className="bar-label">{day.date.slice(8)}</span>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading"><h2>Arizalar holati</h2></div>
          {statusEntries.length ? statusEntries.map(([status, count]) => (
            <div className="status-stat" key={status}>
              <span><i className={`status-dot status-${status}`} />{STATUS_LABELS[status as LeadStatus] || status}</span>
              <strong>{count}</strong>
            </div>
          )) : <EmptyState>Hozircha arizalar mavjud emas.</EmptyState>}
        </section>
        <section className="panel">
          <div className="panel-heading"><h2>Ko'p so'ralgan avtomobillar</h2></div>
          {stats.leads_by_car.length ? stats.leads_by_car.slice(0, 5).map((car, index) => (
            <div className="rank-row" key={`${car.car}-${index}`}>
              <span className="rank-index">{String(index + 1).padStart(2, "0")}</span>
              <span>{car.car}</span>
              <strong>{car.count}</strong>
            </div>
          )) : <EmptyState>Hozircha ma'lumot yo'q.</EmptyState>}
        </section>
      </div>
    </>
  );
}

function KpiCard({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <article className="kpi-card">
      <span>{label}</span>
      <strong>{api.formatNumber(value)}</strong>
      {detail && <small>{detail}</small>}
    </article>
  );
}

function LeadsPage() {
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [carId, setCarId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<"created_at" | "name" | "status">("created_at");
  const [sortDesc, setSortDesc] = useState(true);
  const [applied, setApplied] = useState(new URLSearchParams());
  const carsQuery = useQuery({ queryKey: ["admin-cars"], queryFn: api.getCars });
  const params = new URLSearchParams(applied);
  params.set("limit", "20");
  params.set("offset", String(page * 20));
  const leadsQuery = useQuery({
    queryKey: ["admin-leads", params.toString()],
    queryFn: () => api.getLeads(params),
  });
  const queryClient = useQueryClient();
  const notify = useToast();
  const statusMutation = useMutation({
    mutationFn: ({ id, nextStatus }: { id: number; nextStatus: LeadStatus }) =>
      api.updateLead(id, { status: nextStatus }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-leads"] });
      notify("Ariza holati yangilandi.");
    },
    onError: (error) => notify(error.message, true),
  });

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (status) next.set("status", status);
    if (type) next.set("type", type);
    if (carId) next.set("car_id", carId);
    if (from) next.set("date_from", from);
    if (to) next.set("date_to", to);
    if (search.trim()) next.set("q", search.trim());
    setPage(0);
    setApplied(next);
  }

  function exportCsv() {
    void api.exportLeads(applied).then((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "arizalar.csv";
      link.click();
      URL.revokeObjectURL(url);
    }).catch((error: Error) => notify(error.message, true));
  }

  const sortedLeads = useMemo(() => {
    const items = [...(leadsQuery.data?.items || [])];
    items.sort((left, right) => {
      const a = left[sortKey];
      const b = right[sortKey];
      const comparison = String(a).localeCompare(String(b));
      return sortDesc ? -comparison : comparison;
    });
    return items;
  }, [leadsQuery.data?.items, sortDesc, sortKey]);

  return (
    <section>
      <PageHeader title="Arizalar" description="Mijozlar murojaatlarini ko'rish va boshqarish." action={<button className="button button-secondary" onClick={exportCsv}>CSV eksport</button>} />
      <form className="filter-bar panel" onSubmit={applyFilters}>
        <label>Holati<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Barchasi</option>{Object.entries(STATUS_LABELS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
        <label>Turi<select value={type} onChange={(event) => setType(event.target.value)}><option value="">Barchasi</option>{Object.entries(TYPE_LABELS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
        <label>Avtomobil<select value={carId} onChange={(event) => setCarId(event.target.value)}><option value="">Barchasi</option>{(carsQuery.data || []).map((car) => <option key={car.id} value={car.id}>{car.brand} {car.model}</option>)}</select></label>
        <label>Dan<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
        <label>Gacha<input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
        <label className="filter-search">Ism yoki telefon<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Qidirish" /></label>
        <button className="button button-primary">Filtrlash</button>
      </form>
      {leadsQuery.isPending ? <LoadingState /> : leadsQuery.isError ? (
        <ErrorState error={leadsQuery.error} retry={() => void leadsQuery.refetch()} />
      ) : (
        <>
          <div className="table-toolbar"><span>{leadsQuery.data.total} ta ariza</span></div>
          <LeadTable
            leads={sortedLeads}
            onSelect={(id) => setSelectedId(id)}
            onStatusChange={(id, nextStatus) => statusMutation.mutate({ id, nextStatus })}
            sortKey={sortKey}
            sortDesc={sortDesc}
            onSort={(key) => { setSortDesc(key === sortKey ? !sortDesc : true); setSortKey(key); }}
          />
          <Pagination page={page} total={leadsQuery.data.total} limit={20} onPage={setPage} />
        </>
      )}
      {selectedId !== null && <LeadDrawer id={selectedId} onClose={() => setSelectedId(null)} />}
    </section>
  );
}

function LeadTable({
  leads,
  compact = false,
  onSelect,
  onStatusChange,
  sortKey,
  sortDesc,
  onSort,
}: {
  leads: Lead[];
  compact?: boolean;
  onSelect?: (id: number) => void;
  onStatusChange?: (id: number, status: LeadStatus) => void;
  sortKey?: string;
  sortDesc?: boolean;
  onSort?: (key: "created_at" | "name" | "status") => void;
}) {
  if (!leads.length) return <EmptyState>Bu filtrlar bo'yicha arizalar topilmadi.</EmptyState>;
  const sortButton = (key: "created_at" | "name" | "status", label: string) => (
    <button className="sort-button" onClick={() => onSort?.(key)}>
      {label}{sortKey === key ? (sortDesc ? " ↓" : " ↑") : ""}
    </button>
  );
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr>
          <th>№</th><th>{sortButton("name", "Mijoz")}</th><th>Telefon</th><th>Avtomobil</th><th>Turi</th><th>{sortButton("status", "Holati")}</th><th>{sortButton("created_at", "Sana")}</th>
        </tr></thead>
        <tbody>
          {leads.map((lead) => (
            <tr key={lead.id}>
              <td className="muted">#{lead.id}</td>
              <td><button className="table-link" onClick={() => onSelect?.(lead.id)}>{lead.name}</button></td>
              <td><a href={`tel:${lead.phone}`}>{lead.phone}</a></td>
              <td>{lead.car_id ? `#${lead.car_id}` : "—"}</td>
              <td>{TYPE_LABELS[lead.type]}</td>
              <td>
                {onStatusChange ? (
                  <select
                    className={`status-select status-${lead.status}`}
                    value={lead.status}
                    aria-label={`${lead.name} arizasi holati`}
                    onChange={(event) => onStatusChange(lead.id, event.target.value as LeadStatus)}
                  >
                    {Object.entries(STATUS_LABELS).map(([key, value]) => <option value={key} key={key}>{value}</option>)}
                  </select>
                ) : <span className={`status-pill status-${lead.status}`}>{STATUS_LABELS[lead.status]}</span>}
              </td>
              <td>{formatDate(lead.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {compact && <div className="table-footnote">Jami ko'rsatilgan: {leads.length}</div>}
    </div>
  );
}

function LeadDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const notify = useToast();
  const queryClient = useQueryClient();
  const leadQuery = useQuery({ queryKey: ["admin-lead", id], queryFn: () => api.getLead(id) });
  const [note, setNote] = useState("");
  useEffect(() => {
    if (leadQuery.data) setNote(leadQuery.data.internal_note || "");
  }, [leadQuery.data]);
  const noteMutation = useMutation({
    mutationFn: () => api.updateLead(id, { internal_note: note }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-lead", id] });
      notify("Ichki izoh saqlandi.");
    },
    onError: (error) => notify(error.message, true),
  });

  return (
    <div className="drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="lead-drawer-title">
        <div className="drawer-heading"><h2 id="lead-drawer-title">Ariza tafsilotlari</h2><button className="icon-button" aria-label="Yopish" onClick={onClose}>×</button></div>
        {leadQuery.isPending ? <LoadingState /> : leadQuery.isError ? <ErrorState error={leadQuery.error} /> : (
          <>
            <p className="eyebrow">ARIZA #{leadQuery.data.id}</p>
            <h3>{leadQuery.data.name}</h3>
            <a className="call-card" href={`tel:${leadQuery.data.phone}`}>{leadQuery.data.phone} <span>Qo'ng'iroq qilish</span></a>
            <dl className="detail-list">
              <dt>Turi</dt><dd>{TYPE_LABELS[leadQuery.data.type]}</dd>
              <dt>Holati</dt><dd>{STATUS_LABELS[leadQuery.data.status]}</dd>
              <dt>Avtomobil ID</dt><dd>{leadQuery.data.car_id ?? "Tanlanmagan"}</dd>
              <dt>Komplektatsiya ID</dt><dd>{leadQuery.data.trim_id ?? "Tanlanmagan"}</dd>
              <dt>Yuborilgan vaqt</dt><dd>{formatDate(leadQuery.data.created_at)}</dd>
              <dt>Mijoz izohi</dt><dd>{leadQuery.data.comment || "Izoh qoldirilmagan"}</dd>
            </dl>
            <label className="field-block">Ichki izoh<textarea rows={5} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Faqat xodimlar uchun" /></label>
            <button className="button button-primary button-wide" disabled={noteMutation.isPending} onClick={() => noteMutation.mutate()}>
              {noteMutation.isPending ? "Saqlanmoqda…" : "Izohni saqlash"}
            </button>
          </>
        )}
      </aside>
    </div>
  );
}

function Pagination({ page, total, limit, onPage }: { page: number; total: number; limit: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="pagination">
      <span>{total ? `${page * limit + 1}–${Math.min((page + 1) * limit, total)} / ${total}` : "0 ta natija"}</span>
      <div>
        <button className="button button-secondary" disabled={page === 0} onClick={() => onPage(page - 1)}>Oldingi</button>
        <span className="page-number">{page + 1} / {pages}</span>
        <button className="button button-secondary" disabled={(page + 1) * limit >= total} onClick={() => onPage(page + 1)}>Keyingi</button>
      </div>
    </div>
  );
}

function CarsPage() {
  const [editing, setEditing] = useState<Car | null | "new">(null);
  const { admin } = useAuth();
  const notify = useToast();
  const queryClient = useQueryClient();
  const carsQuery = useQuery({ queryKey: ["admin-cars"], queryFn: api.getCars });
  const activeMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => api.setCarActive(id, active),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-cars"] });
      notify("Avtomobil holati yangilandi.");
    },
    onError: (error) => notify(error.message, true),
  });
  const deleteMutation = useMutation({
    mutationFn: api.deleteCar,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-cars"] });
      notify("Avtomobil o'chirildi.");
    },
    onError: (error) => notify(error.message, true),
  });

  function deleteCar(car: Car) {
    if (admin?.role !== "owner") return;
    if (window.confirm(`${car.brand} ${car.model} avtomobilini o'chirmoqchimisiz?`)) {
      deleteMutation.mutate(car.id);
    }
  }

  return (
    <section>
      <PageHeader title="Avtomobillar" description="Katalog, komplektatsiyalar va rasmlarni boshqarish." action={<button className="button button-primary" onClick={() => setEditing("new")}>Avtomobil qo'shish</button>} />
      {carsQuery.isPending ? <LoadingState /> : carsQuery.isError ? <ErrorState error={carsQuery.error} retry={() => void carsQuery.refetch()} /> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Muqova</th><th>Model</th><th>Tur</th><th>Komplektatsiyalar</th><th>Holati</th><th>Amallar</th></tr></thead>
            <tbody>{carsQuery.data.map((car) => (
              <tr key={car.id}>
                <td>{car.images.length ? <img className="table-thumb" src={api.imageUrl(car.images.find((image) => image.is_cover)?.thumbnail_path || car.images[0].thumbnail_path || car.images[0].path)} alt="" /> : <div className="thumb-empty">Rasm yo'q</div>}</td>
                <td><strong>{car.brand} {car.model}</strong><small className="table-subline">{car.slug}</small></td>
                <td>{car.body_type} · {car.drive}</td>
                <td>{car.trims.length} ta</td>
                <td>
                  <button
                    className={`toggle ${car.is_active ? "toggle-on" : ""}`}
                    role="switch"
                    aria-checked={car.is_active}
                    aria-label={`${car.brand} ${car.model} ${car.is_active ? "faol" : "faol emas"}`}
                    disabled={activeMutation.isPending}
                    onClick={() => activeMutation.mutate({ id: car.id, active: !car.is_active })}
                  ><span /></button>
                  <span className="muted">{car.is_active ? "Faol" : "Yashirin"}</span>
                </td>
                <td className="row-actions">
                  <button className="button button-secondary" onClick={() => setEditing(car)}>Tahrirlash</button>
                  {admin?.role === "owner" && <button className="button button-danger-quiet" onClick={() => deleteCar(car)}>O'chirish</button>}
                </td>
              </tr>
            ))}</tbody>
          </table>
          {!carsQuery.data.length && <EmptyState>Katalogda avtomobillar yo'q.</EmptyState>}
        </div>
      )}
      {editing && <CarEditor car={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

type CarFormState = Omit<Car, "id" | "trims" | "images">;
const EMPTY_CAR: CarFormState = {
  slug: "", brand: "Volkswagen", model: "", body_type: "", engine: "",
  power_hp: 1, emission: "Euro-6", drive: "FWD", transmission: "",
  seats: 5, description: "", is_active: true, sort_order: 0,
};

function CarEditor({ car, onClose }: { car: Car | null; onClose: () => void }) {
  const notify = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CarFormState>(() => {
    if (!car) return EMPTY_CAR;
    return {
      slug: car.slug,
      brand: car.brand,
      model: car.model,
      body_type: car.body_type,
      engine: car.engine,
      power_hp: car.power_hp,
      emission: car.emission,
      drive: car.drive,
      transmission: car.transmission,
      seats: car.seats,
      description: car.description,
      is_active: car.is_active,
      sort_order: car.sort_order,
    };
  });
  const saveMutation = useMutation({
    mutationFn: () => api.saveCar(form, car?.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-cars"] });
      notify("Avtomobil ma'lumotlari saqlandi.");
      onClose();
    },
    onError: (error) => notify(error.message, true),
  });

  function change<K extends keyof CarFormState>(key: K, value: CarFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="drawer drawer-wide" role="dialog" aria-modal="true" aria-labelledby="car-editor-title">
        <div className="drawer-heading"><h2 id="car-editor-title">{car ? "Avtomobilni tahrirlash" : "Yangi avtomobil"}</h2><button className="icon-button" aria-label="Yopish" onClick={onClose}>×</button></div>
        <form className="form-grid" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
          <label>Slug<input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={form.slug} onChange={(event) => change("slug", event.target.value)} /></label>
          <label>Brend<input required value={form.brand} onChange={(event) => change("brand", event.target.value)} /></label>
          <label>Model<input required value={form.model} onChange={(event) => change("model", event.target.value)} /></label>
          <label>Kuzov turi<input required value={form.body_type} onChange={(event) => change("body_type", event.target.value)} placeholder="C-SUV" /></label>
          <label>Dvigatel<input required value={form.engine} onChange={(event) => change("engine", event.target.value)} /></label>
          <label>Quvvat (o.k.)<input type="number" min="1" required value={form.power_hp} onChange={(event) => change("power_hp", Number(event.target.value))} /></label>
          <label>Ekologik standart<input required value={form.emission} onChange={(event) => change("emission", event.target.value)} /></label>
          <label>Uzatma<select value={form.drive} onChange={(event) => change("drive", event.target.value as CarFormState["drive"])}><option value="AWD">AWD</option><option value="FWD">FWD</option></select></label>
          <label>Transmissiya<input required value={form.transmission} onChange={(event) => change("transmission", event.target.value)} /></label>
          <label>O'rindiqlar<input type="number" min="1" max="20" required value={form.seats} onChange={(event) => change("seats", Number(event.target.value))} /></label>
          <label>Tartib raqami<input type="number" min="0" value={form.sort_order} onChange={(event) => change("sort_order", Number(event.target.value))} /></label>
          <label className="form-grid-wide">Tavsif<textarea rows={3} value={form.description || ""} onChange={(event) => change("description", event.target.value || null)} /></label>
          <label className="check-label form-grid-wide"><input type="checkbox" checked={form.is_active} onChange={(event) => change("is_active", event.target.checked)} /> Katalogda faol ko'rsatish</label>
          <div className="form-grid-wide form-actions">
            <button type="button" className="button button-secondary" onClick={onClose}>Bekor qilish</button>
            <button className="button button-primary" disabled={saveMutation.isPending}>{saveMutation.isPending ? "Saqlanmoqda…" : "Saqlash"}</button>
          </div>
        </form>
        {car && <div className="editor-subsection">
          <TrimEditor car={car} />
          <ImageManager car={car} />
        </div>}
      </aside>
    </div>
  );
}

function PriceInput({ value, onChange }: { value: number | null; onChange: (value: number | null) => void }) {
  const [text, setText] = useState(value === null ? "" : api.formatNumber(value));
  const [notAnnounced, setNotAnnounced] = useState(value === null);
  useEffect(() => {
    setText(value === null ? "" : api.formatNumber(value));
    setNotAnnounced(value === null);
  }, [value]);
  return (
    <div className="price-input">
      <input
        inputMode="numeric"
        disabled={notAnnounced}
        aria-label="Narx so'mda"
        value={text}
        onChange={(event) => {
          const digits = event.target.value.replace(/\D/g, "");
          setText(digits ? api.formatNumber(Number(digits)) : "");
          onChange(digits ? Number(digits) : null);
        }}
      />
      <label className="check-label"><input type="checkbox" checked={notAnnounced} onChange={(event) => {
        setNotAnnounced(event.target.checked);
        if (event.target.checked) {
          setText("");
          onChange(null);
        }
      }} /> Narxi e'lon qilinmagan</label>
    </div>
  );
}

function TrimEditor({ car }: { car: Car }) {
  const notify = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [price, setPrice] = useState<number | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-cars"] });
  const addMutation = useMutation({
    mutationFn: () => api.addTrim(car.id, { name: name.trim(), price }),
    onSuccess: () => { setName(""); setPrice(null); void refresh(); notify("Komplektatsiya qo'shildi."); },
    onError: (error) => notify(error.message, true),
  });
  const deleteMutation = useMutation({
    mutationFn: api.deleteTrim,
    onSuccess: () => { void refresh(); notify("Komplektatsiya o'chirildi."); },
    onError: (error) => notify(error.message, true),
  });
  const [items, setItems] = useState<Trim[]>(car.trims);
  const [prices, setPrices] = useState<Record<number, number | null>>(
    () => Object.fromEntries(car.trims.map((trim) => [trim.id, trim.price])),
  );
  useEffect(() => setItems(car.trims), [car.trims]);
  useEffect(() => {
    setPrices(Object.fromEntries(car.trims.map((trim) => [trim.id, trim.price])));
  }, [car.trims]);

  function move(index: number, direction: -1 | 1) {
    const next = [...items];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setItems(next);
    void Promise.all(next.map((trim, position) => api.updateTrim(trim.id, { sort_order: position })))
      .then(refresh)
      .catch((error: Error) => notify(error.message, true));
  }

  return (
    <section className="subsection">
      <div className="panel-heading"><h3>Komplektatsiyalar</h3></div>
      {items.map((trim, index) => (
        <div className="trim-row" key={trim.id}>
          <input
            aria-label="Komplektatsiya nomi"
            defaultValue={trim.name}
            onBlur={(event) => {
              const nextName = event.target.value.trim();
              if (nextName && nextName !== trim.name) {
                void api.updateTrim(trim.id, { name: nextName }).then(refresh).catch((error: Error) => notify(error.message, true));
              }
            }}
          />
          <PriceInput
            value={trim.price}
            onChange={(nextPrice) => setPrices((current) => ({ ...current, [trim.id]: nextPrice }))}
          />
          <div className="trim-actions">
            <button className="button button-secondary" aria-label="Yuqoriga" onClick={() => move(index, -1)}>↑</button>
            <button className="button button-secondary" aria-label="Pastga" onClick={() => move(index, 1)}>↓</button>
            <button className="button button-secondary" onClick={() => {
              void api.updateTrim(trim.id, { price: prices[trim.id] }).then(refresh).then(() => notify("Narx saqlandi.")).catch((error: Error) => notify(error.message, true));
            }}>Narxni saqlash</button>
            <button className="button button-danger-quiet" aria-label={`${trim.name}ni o'chirish`} onClick={() => {
              if (window.confirm(`${trim.name} komplektatsiyasini o'chirasizmi?`)) deleteMutation.mutate(trim.id);
            }}>O'chirish</button>
          </div>
        </div>
      ))}
      <form className="trim-add" onSubmit={(event) => { event.preventDefault(); addMutation.mutate(); }}>
        <input required value={name} onChange={(event) => setName(event.target.value)} placeholder="Yangi komplektatsiya nomi" />
        <PriceInput value={price} onChange={setPrice} />
        <button className="button button-secondary" disabled={addMutation.isPending}>Qo'shish</button>
      </form>
    </section>
  );
}

function ImageManager({ car }: { car: Car }) {
  const notify = useToast();
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-cars"] });
  const [dragActive, setDragActive] = useState(false);
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => api.uploadCarImages(car.id, files),
    onSuccess: () => { void refresh(); notify("Rasmlar yuklandi."); },
    onError: (error) => notify(error.message, true),
  });
  const coverMutation = useMutation({
    mutationFn: (imageId: number) => api.setCover(car.id, imageId),
    onSuccess: () => void refresh(),
    onError: (error) => notify(error.message, true),
  });
  const deleteMutation = useMutation({
    mutationFn: (imageId: number) => api.deleteImage(car.id, imageId),
    onSuccess: () => { void refresh(); notify("Rasm o'chirildi."); },
    onError: (error) => notify(error.message, true),
  });
  const [images, setImages] = useState<CarImage[]>(car.images);
  useEffect(() => setImages(car.images), [car.images]);

  function reorder(next: CarImage[]) {
    setImages(next);
    void api.reorderImages(car.id, next.map((image) => image.id))
      .then(refresh)
      .catch((error: Error) => notify(error.message, true));
  }

  return (
    <section className="subsection">
      <div className="panel-heading"><h3>Rasmlar</h3><span className="muted">JPEG, PNG yoki WebP · 5 MB gacha</span></div>
      <label
        className={`drop-zone ${dragActive ? "drop-zone-active" : ""}`}
        onDragOver={(event) => { event.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragActive(false);
          const files = Array.from(event.dataTransfer.files);
          if (files.length) uploadMutation.mutate(files);
        }}
      >
        <input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => {
          if (event.target.files?.length) uploadMutation.mutate(Array.from(event.target.files));
          event.target.value = "";
        }} />
        {uploadMutation.isPending ? "Rasmlar yuklanmoqda…" : "Rasmlarni shu yerga tashlang yoki tanlash uchun bosing"}
      </label>
      <div className="image-manager-grid">
        {images.map((image, index) => (
          <article
            className="image-manager-card"
            key={image.id}
            draggable
            onDragStart={(event) => event.dataTransfer.setData("text/plain", String(index))}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const source = Number(event.dataTransfer.getData("text/plain"));
              if (!Number.isInteger(source) || source === index) return;
              const next = [...images];
              const [moved] = next.splice(source, 1);
              next.splice(index, 0, moved);
              reorder(next);
            }}
          >
            <img src={api.imageUrl(image.thumbnail_path || image.path)} alt={`${car.model} rasmi`} />
            {image.is_cover && <span className="cover-label">Muqova</span>}
            <div className="image-actions">
              {!image.is_cover && <button className="button button-secondary" onClick={() => coverMutation.mutate(image.id)}>Muqova qilish</button>}
              <button className="button button-danger-quiet" onClick={() => {
                if (window.confirm("Rasm va uning fayllarini o'chirasizmi?")) deleteMutation.mutate(image.id);
              }}>O'chirish</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function UsersPage() {
  const [search, setSearch] = useState("");
  const [applied, setApplied] = useState("");
  const [page, setPage] = useState(0);
  const queryClient = useQueryClient();
  const notify = useToast();
  const params = new URLSearchParams({ limit: "20", offset: String(page * 20) });
  if (applied) params.set("q", applied);
  const usersQuery = useQuery({
    queryKey: ["admin-users", params.toString()],
    queryFn: () => api.getUsers(params),
  });
  const blockMutation = useMutation({
    mutationFn: ({ id, blocked }: { id: number; blocked: boolean }) => api.setUserBlocked(id, blocked),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["admin-users"] }); notify("Foydalanuvchi holati yangilandi."); },
    onError: (error) => notify(error.message, true),
  });

  return (
    <section>
      <PageHeader title="Foydalanuvchilar" description="Telegram orqali ro'yxatdan o'tgan mijozlar." />
      <form className="search-bar panel" onSubmit={(event) => { event.preventDefault(); setPage(0); setApplied(search.trim()); }}>
        <label>Ism, username yoki telefon<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Qidirish" /></label>
        <button className="button button-primary">Qidirish</button>
      </form>
      {usersQuery.isPending ? <LoadingState /> : usersQuery.isError ? <ErrorState error={usersQuery.error} retry={() => void usersQuery.refetch()} /> : (
        <>
          <div className="table-wrap">
            <table className="data-table"><thead><tr><th>Foydalanuvchi</th><th>Telefon</th><th>Telegram ID</th><th>Til</th><th>Ro'yxatdan o'tgan</th><th>Holati</th><th>Amal</th></tr></thead>
              <tbody>{usersQuery.data.items.map((user) => (
                <tr key={user.id}>
                  <td><strong>{user.name || "Ism ko'rsatilmagan"}</strong>{user.username && <small className="table-subline">@{user.username}</small>}</td>
                  <td>{user.phone ? <a href={`tel:${user.phone}`}>{user.phone}</a> : "—"}</td>
                  <td>{user.tg_id ?? "—"}</td><td>{user.language}</td><td>{formatDate(user.created_at)}</td>
                  <td><span className={`status-pill ${user.is_blocked ? "status-cancelled" : "status-done"}`}>{user.is_blocked ? "Bloklangan" : "Faol"}</span></td>
                  <td><button className={`button ${user.is_blocked ? "button-secondary" : "button-danger-quiet"}`} onClick={() => {
                    const verb = user.is_blocked ? "blokdan chiqarmoqchimisiz" : "bloklamoqchimisiz";
                    if (window.confirm(`${user.name || "Foydalanuvchi"}ni ${verb}?`)) {
                      blockMutation.mutate({ id: user.id, blocked: !user.is_blocked });
                    }
                  }}>{user.is_blocked ? "Blokdan chiqarish" : "Bloklash"}</button></td>
                </tr>
              ))}</tbody>
            </table>
            {!usersQuery.data.items.length && <EmptyState>Foydalanuvchilar topilmadi.</EmptyState>}
          </div>
          <Pagination page={page} total={usersQuery.data.total} limit={20} onPage={setPage} />
        </>
      )}
    </section>
  );
}

function BroadcastPage() {
  const notify = useToast();
  const [text, setText] = useState("");
  const [segment, setSegment] = useState("all");
  const [miniAppButton, setMiniAppButton] = useState(false);
  const [image, setImage] = useState<File | null>(null);
  const [broadcastId, setBroadcastId] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const sendMutation = useMutation({
    mutationFn: (form: FormData) => api.sendBroadcast(form),
    onSuccess: (result) => { setBroadcastId(result.broadcast_id); notify("Xabar yuborish navbatga qo'yildi."); },
    onError: (error) => notify(error.message, true),
  });
  const progressQuery = useQuery({
    queryKey: ["broadcast-progress", broadcastId],
    queryFn: () => api.getBroadcastProgress(broadcastId),
    enabled: Boolean(broadcastId),
    refetchInterval: (query) => {
      const state = query.state.data?.status;
      return state === "completed" || state === "failed" ? false : 1200;
    },
  });

  useEffect(() => {
    if (!image) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(image);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    if (!window.confirm("Xabarni tanlangan foydalanuvchilarga yuborishni boshlaysizmi?")) return;
    const form = new FormData();
    form.set("text", text.trim());
    form.set("segment", segment);
    form.set("mini_app_button", String(miniAppButton));
    if (image) form.set("image", image);
    setBroadcastId("");
    sendMutation.mutate(form);
  }

  const progress = progressQuery.data;
  const percent = progress && progress.total ? Math.round((progress.processed / progress.total) * 100) : 0;
  return (
    <section>
      <PageHeader title="Xabar yuborish" description="Tanlangan mijozlarga Telegram orqali xabar jo'nating." />
      <div className="two-column">
        <form className="panel stack-form" onSubmit={submit}>
          <label>Xabar matni<textarea rows={8} maxLength={4096} required value={text} onChange={(event) => setText(event.target.value)} placeholder="Mijozlarga yuboriladigan xabar…" /></label>
          <div className="muted align-right">{text.length} / 4096</div>
          <label>Auditoriya<select value={segment} onChange={(event) => setSegment(event.target.value)}><option value="all">Barcha foydalanuvchilar</option><option value="with_leads">Ariza qoldirganlar</option><option value="without_leads">Ariza qoldirmaganlar</option></select></label>
          <label>Rasm (ixtiyoriy)<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setImage(event.target.files?.[0] || null)} /></label>
          <label className="check-label"><input type="checkbox" checked={miniAppButton} onChange={(event) => setMiniAppButton(event.target.checked)} /> Mini Appni ochish tugmasini qo'shish</label>
          <button className="button button-primary" disabled={sendMutation.isPending || !text.trim()}>{sendMutation.isPending ? "Yuborilmoqda…" : "Tasdiqlash va yuborish"}</button>
        </form>
        <section className="panel broadcast-preview">
          <div className="panel-heading"><h2>Xabar ko'rinishi</h2></div>
          <div className="telegram-preview">
            {previewUrl && <img src={previewUrl} alt="Xabar rasmi ko'rinishi" />}
            <p>{text || "Xabar matni shu yerda ko'rinadi."}</p>
            {miniAppButton && <button className="preview-webapp">Katalogni ochish</button>}
          </div>
          {progress && <div className="broadcast-progress">
            <div className="panel-heading"><h3>{progress.status === "completed" ? "Yuborish yakunlandi" : progress.status === "failed" ? "Yuborishda xatolik" : "Yuborish jarayoni"}</h3><span>{percent}%</span></div>
            <div className="progress-track"><span style={{ width: `${percent}%` }} /></div>
            <div className="progress-counts"><span>Yuborildi <b>{progress.sent}</b></span><span>Xato <b>{progress.failed}</b></span><span>Bloklangan <b>{progress.blocked}</b></span></div>
            {progress.error && <p className="form-error">{progress.error}</p>}
          </div>}
          {progressQuery.isError && <ErrorState error={progressQuery.error} />}
        </section>
      </div>
    </section>
  );
}

function SettingsPage() {
  const notify = useToast();
  const settingsQuery = useQuery({ queryKey: ["admin-settings"], queryFn: api.getSettings });
  const [form, setForm] = useState<AppSettings | null>(null);
  useEffect(() => { if (settingsQuery.data) setForm(settingsQuery.data); }, [settingsQuery.data]);
  const saveMutation = useMutation({
    mutationFn: api.saveSettings,
    onSuccess: (saved) => { setForm(saved); notify("Sozlamalar saqlandi."); },
    onError: (error) => notify(error.message, true),
  });
  if (settingsQuery.isPending) return <LoadingState />;
  if (settingsQuery.isError) return <ErrorState error={settingsQuery.error} retry={() => void settingsQuery.refetch()} />;
  if (!form) return <EmptyState>Sozlamalarni ochib bo'lmadi.</EmptyState>;

  function update<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    setForm((current) => current ? { ...current, [key]: value } : current);
  }
  return (
    <section>
      <PageHeader title="Sozlamalar" description="Ommaviy aloqa va kredit kalkulyatori ma'lumotlari." />
      <form className="panel settings-form" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(form); }}>
        <label>Manzil<input required value={form.address} onChange={(event) => update("address", event.target.value)} /></label>
        <label>Telefonlar <small>Har birini yangi qatordan kiriting</small><textarea rows={3} value={form.phones.join("\n")} onChange={(event) => update("phones", event.target.value.split("\n").map((phone) => phone.trim()).filter(Boolean))} /></label>
        <label>Xarita havolasi<input value={form.map_link || ""} onChange={(event) => update("map_link", event.target.value || null)} placeholder="https://" /></label>
        <label>Instagram<input value={form.instagram} onChange={(event) => update("instagram", event.target.value)} /></label>
        <label>Ish vaqti<input value={form.working_hours || ""} onChange={(event) => update("working_hours", event.target.value || null)} /></label>
        <label>Kreditning yillik stavkasi, %<input type="number" min="0" max="100" step="0.1" value={form.annual_interest_rate ?? ""} onChange={(event) => update("annual_interest_rate", event.target.value ? Number(event.target.value) : null)} /></label>
        <label className="form-grid-wide">Banner matni<textarea rows={3} value={form.banner_text || ""} onChange={(event) => update("banner_text", event.target.value || null)} /></label>
        <div className="form-grid-wide form-actions"><button className="button button-primary" disabled={saveMutation.isPending}>{saveMutation.isPending ? "Saqlanmoqda…" : "Saqlash"}</button></div>
      </form>
    </section>
  );
}

function AuditPage() {
  const [page, setPage] = useState(0);
  const params = new URLSearchParams({ limit: "25", offset: String(page * 25) });
  const auditQuery = useQuery({
    queryKey: ["admin-audit", params.toString()],
    queryFn: () => api.getAudit(params),
  });
  return (
    <section>
      <PageHeader title="Audit jurnali" description="Adminlar bajargan amallar tarixi." />
      {auditQuery.isPending ? <LoadingState /> : auditQuery.isError ? <ErrorState error={auditQuery.error} retry={() => void auditQuery.refetch()} /> : (
        <>
          <div className="table-wrap"><table className="data-table"><thead><tr><th>Sana</th><th>Admin ID</th><th>Amal</th><th>Obyekt</th><th>Obyekt ID</th><th>IP</th></tr></thead>
            <tbody>{auditQuery.data.items.map((entry) => <tr key={entry.id}><td>{formatDate(entry.created_at)}</td><td>{entry.admin_user_id ?? "—"}</td><td>{entry.action}</td><td>{entry.entity}</td><td>{entry.entity_id ?? "—"}</td><td>{entry.ip_address ?? "—"}</td></tr>)}</tbody>
          </table>{!auditQuery.data.items.length && <EmptyState>Audit yozuvlari hozircha yo'q.</EmptyState>}</div>
          <Pagination page={page} total={auditQuery.data.total} limit={25} onPage={setPage} />
        </>
      )}
    </section>
  );
}

function AccountsPage() {
  const notify = useToast();
  const queryClient = useQueryClient();
  const accountsQuery = useQuery({ queryKey: ["admin-accounts"], queryFn: api.getAdminAccounts });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const createMutation = useMutation({
    mutationFn: () => api.createManager(username.trim(), password),
    onSuccess: () => {
      setUsername("");
      setPassword("");
      void queryClient.invalidateQueries({ queryKey: ["admin-accounts"] });
      notify("Manager hisobi yaratildi.");
    },
    onError: (error) => notify(error.message, true),
  });
  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => api.setAdminActive(id, active),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["admin-accounts"] }); notify("Admin holati yangilandi."); },
    onError: (error) => notify(error.message, true),
  });

  function resetPassword(account: AdminAccount) {
    const nextPassword = window.prompt(`${account.username} uchun yangi parolni kiriting (kamida 12 belgi):`);
    if (nextPassword === null) return;
    if (nextPassword.length < 12) {
      notify("Parol kamida 12 belgidan iborat bo'lishi kerak.", true);
      return;
    }
    void api.resetAdminPassword(account.id, nextPassword)
      .then(() => notify("Parol yangilandi."))
      .catch((error: Error) => notify(error.message, true));
  }

  return (
    <section>
      <PageHeader title="Admin hisoblari" description="Manager hisoblarini boshqarish." />
      <form className="panel account-create" onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}>
        <label>Foydalanuvchi nomi<input required minLength={3} value={username} onChange={(event) => setUsername(event.target.value)} /></label>
        <label>Vaqtinchalik parol<input required minLength={12} type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        <button className="button button-primary" disabled={createMutation.isPending}>Manager qo'shish</button>
      </form>
      {accountsQuery.isPending ? <LoadingState /> : accountsQuery.isError ? <ErrorState error={accountsQuery.error} retry={() => void accountsQuery.refetch()} /> : (
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Login</th><th>Rol</th><th>Holati</th><th>Yaratilgan</th><th>Amallar</th></tr></thead>
          <tbody>{accountsQuery.data.map((account) => <tr key={account.id}>
            <td>{account.username}</td><td>{account.role === "owner" ? "Owner" : "Manager"}</td><td>{account.is_active ? "Faol" : "Faol emas"}</td><td>{formatDate(account.created_at)}</td>
            <td className="row-actions">{account.role === "manager" && <>
              <button className="button button-secondary" onClick={() => resetPassword(account)}>Parolni yangilash</button>
              <button className="button button-danger-quiet" onClick={() => {
                if (window.confirm(`${account.username} hisobini ${account.is_active ? "o'chirasizmi" : "faollashtirasizmi"}?`)) toggleMutation.mutate({ id: account.id, active: !account.is_active });
              }}>{account.is_active ? "O'chirish" : "Faollashtirish"}</button>
            </>}</td>
          </tr>)}</tbody>
        </table>{!accountsQuery.data.length && <EmptyState>Admin hisoblari topilmadi.</EmptyState>}</div>
      )}
    </section>
  );
}

function ForbiddenPage() {
  return <div className="state-card state-error"><strong>Ruxsat yo'q</strong><span>Bu bo'lim faqat owner uchun ochiq.</span></div>;
}

function NotFoundPage() {
  return <div className="state-card"><strong>Sahifa topilmadi</strong><Link to="/">Bosh sahifaga qaytish</Link></div>;
}

export default App;
