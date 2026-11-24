import {
  useCallback,
  type FormEvent,
  type Ref,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";
import type { LeadPayload } from "./api";
import type { Car, CreditResult, LeadType } from "./types";
import {
  getTelegramWebApp,
  hapticSelection,
  hapticSuccess,
} from "./telegram";
import { t } from "./i18n";

type Screen = "home" | "detail" | "compare" | "credit" | "request" | "success" | "favorites" | "contacts";
type SortMode = "popular" | "price_asc" | "price_desc";
type BodyFilter = "all" | "suv" | "sedan";

const PRICE_MILLION = 1_000_000;
const DEFAULT_PRICE_MAX = 900 * PRICE_MILLION;

function priceText(price: number | null): string {
  return api.formatPrice(price);
}

function carName(car: Car): string {
  return `${car.brand} ${car.model}`;
}

function priceRange(car: Car): string {
  const prices = car.trims
    .map((trim) => trim.price)
    .filter((price): price is number => price !== null);
  if (!prices.length) return t("laterPrice");
  return `${priceText(Math.min(...prices))} — ${priceText(Math.max(...prices))}`;
}

function lowestPrice(car: Car): number | null {
  const prices = car.trims
    .map((trim) => trim.price)
    .filter((price): price is number => price !== null);
  return prices.length ? Math.min(...prices) : null;
}

function estimateCredit(
  result: CreditResult,
  initialPercent: number,
  months: number,
): CreditResult {
  const initialPayment = Math.round(result.amount * initialPercent / 100);
  const loanAmount = result.amount - initialPayment;
  const monthlyRate = result.annual_rate / 1200;
  const factor = (1 + monthlyRate) ** months;
  const monthlyPayment = monthlyRate
    ? Math.round(loanAmount * monthlyRate * factor / (factor - 1))
    : Math.round(loanAmount / months);
  return {
    ...result,
    initial_percent: initialPercent,
    initial_payment: initialPayment,
    loan_amount: loanAmount,
    months,
    monthly_payment: monthlyPayment,
  };
}

function imageFor(car: Car, index = 0): string | undefined {
  const directImage = api.imageUrl(car.image_url);
  if (index === 0 && directImage) return directImage;
  const images = [...car.images].sort((a, b) => a.sort_order - b.sort_order);
  const image = images[index] || images.find((item) => item.is_cover);
  return api.imageUrl(image?.thumbnail_path || image?.path || car.image_url);
}

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [authMessage, setAuthMessage] = useState("");
  const webApp = getTelegramWebApp();
  const telegramUser = webApp?.initDataUnsafe.user;

  useEffect(() => {
    if (!webApp) return;
    if (!webApp.initData) {
      setAuthMessage(t("authError"));
      return;
    }
    let active = true;
    api.authenticate(webApp.initData)
      .then((result) => {
        if (active) setToken(result.access_token);
      })
      .catch((error: unknown) => {
        if (active) setAuthMessage(error instanceof Error ? error.message : t("authError"));
      });
    return () => {
      active = false;
    };
  }, [webApp]);

  if (!webApp) {
    return (
      <main className="outside-page">
        <div className="outside-card">
          <p className="app-eyebrow">{t("eyebrow")}</p>
          <h1>{t("outsideTitle")}</h1>
          <p>{t("outsideText")}</p>
        </div>
      </main>
    );
  }

  if (!token) {
    return (
      <main className="center-state">
        {authMessage ? (
          <div className="state-card state-error" role="alert">
            <h1>{t("authError")}</h1>
            <p>{authMessage}</p>
            <button className="secondary-button" onClick={() => window.location.reload()}>{t("retry")}</button>
          </div>
        ) : <p role="status">{t("loading")}</p>}
      </main>
    );
  }

  return <Showroom token={token} customerName={telegramUser?.first_name || ""} />;
}

function Showroom({ token, customerName }: { token: string; customerName: string }) {
  const [screen, setScreen] = useState<Screen>("home");
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [bodyFilter, setBodyFilter] = useState<BodyFilter>("all");
  const [driveFilter, setDriveFilter] = useState<"all" | "AWD" | "FWD">("all");
  const [engineFilter, setEngineFilter] = useState("");
  const [priceMin, setPriceMin] = useState(0);
  const [priceMax, setPriceMax] = useState(DEFAULT_PRICE_MAX);
  const [budgetAmount, setBudgetAmount] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("popular");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [heroIndex, setHeroIndex] = useState(0);
  const [comparisonIds, setComparisonIds] = useState<number[]>([]);
  const [creditCarId, setCreditCarId] = useState<number | null>(null);
  const [creditTrimId, setCreditTrimId] = useState<number | null>(null);
  const [requestType, setRequestType] = useState<LeadType>("test_drive");
  const [requestCarId, setRequestCarId] = useState<number | null>(null);
  const [requestTrimId, setRequestTrimId] = useState<number | null>(null);
  const [requestPhone, setRequestPhone] = useState("");
  const [requestError, setRequestError] = useState("");
  const [monthlyResult, setMonthlyResult] = useState<CreditResult | null>(null);
  const [activeImage, setActiveImage] = useState(0);
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const leadForm = useRef<HTMLFormElement>(null);
  const queryClient = useQueryClient();

  const carsQuery = useQuery({
    queryKey: ["cars", token],
    queryFn: () => api.getCars(token),
  });
  const cars = useMemo(() => carsQuery.data || [], [carsQuery.data]);
  const availablePrices = useMemo(
    () => cars.flatMap((car) => car.trims.map((trim) => trim.price).filter((price): price is number => price !== null)),
    [cars],
  );
  const sliderMax = Math.max(
    DEFAULT_PRICE_MAX,
    Math.ceil(Math.max(...availablePrices, DEFAULT_PRICE_MAX) / (100 * PRICE_MILLION)) * 100 * PRICE_MILLION,
  );
  useEffect(() => {
    setPriceMax((current) => current === DEFAULT_PRICE_MAX ? sliderMax : Math.min(current, sliderMax));
  }, [sliderMax]);
  const activeFilterCount = Number(bodyFilter !== "all")
    + Number(driveFilter !== "all")
    + Number(Boolean(engineFilter.trim()))
    + Number(priceMin > 0 || priceMax < sliderMax)
    + Number(Boolean(budgetAmount));
  const selectedCar = cars.find((car) => car.slug === selectedSlug) || null;
  const favoriteQuery = useQuery({
    queryKey: ["favorites", token],
    queryFn: () => api.getFavorites(token),
  });
  const contactsQuery = useQuery({
    queryKey: ["contacts", token],
    queryFn: () => api.getContacts(token),
    enabled: screen === "contacts",
  });
  const comparisonQuery = useQuery({
    queryKey: ["compare", token, comparisonIds],
    queryFn: () => api.getComparedCars(token, comparisonIds),
    enabled: screen === "compare" && comparisonIds.length >= 2,
  });

  const favoriteIds = useMemo(
    () => new Set((favoriteQuery.data || []).map((car) => car.id)),
    [favoriteQuery.data],
  );
  const visibleCars = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    const engineQuery = engineFilter.trim().toLocaleLowerCase();
    const maxBudget = Number(budgetAmount) * PRICE_MILLION;
    const hasPriceFilter = priceMin > 0 || priceMax < sliderMax || maxBudget > 0;
    const filtered = cars.filter((car) => {
      const matchesSearch = !query || `${car.brand} ${car.model} ${car.engine}`.toLocaleLowerCase().includes(query);
      const type = car.body_type.toLocaleLowerCase();
      const matchesBody = bodyFilter === "all" || (bodyFilter === "suv" ? type.includes("suv") : type.includes("sedan"));
      const matchesDrive = driveFilter === "all"
        || car.drive.toUpperCase().includes(driveFilter);
      const matchesEngine = !engineQuery || car.engine.toLocaleLowerCase().includes(engineQuery);
      const numericPrices = car.trims.map((trim) => trim.price).filter((price): price is number => price !== null);
      const matchesPrice = !hasPriceFilter || numericPrices.some((price) => (
        price >= priceMin && price <= priceMax && (!maxBudget || price <= maxBudget)
      ));
      return matchesSearch && matchesBody && matchesDrive && matchesEngine && matchesPrice;
    });
    if (sortMode === "popular") return filtered;
    return [...filtered].sort((left, right) => {
      const leftPrice = lowestPrice(left);
      const rightPrice = lowestPrice(right);
      if (leftPrice === null) return 1;
      if (rightPrice === null) return -1;
      return sortMode === "price_asc" ? leftPrice - rightPrice : rightPrice - leftPrice;
    });
  }, [bodyFilter, budgetAmount, cars, driveFilter, engineFilter, priceMax, priceMin, search, sliderMax, sortMode]);
  const heroCars = cars.slice(0, 3);
  const unpricedCars = cars.filter((car) => car.trims.every((trim) => trim.price === null));

  const favoriteMutation = useMutation({
    mutationFn: ({ carId, isFavorite }: { carId: number; isFavorite: boolean }) =>
      isFavorite ? api.removeFavorite(token, carId) : api.addFavorite(token, carId),
    onSuccess: () => {
      hapticSelection();
      void queryClient.invalidateQueries({ queryKey: ["favorites", token] });
    },
  });
  const creditMutation = useMutation({
    mutationFn: () => {
      if (creditCarId === null || creditTrimId === null) throw new Error(t("chooseTrim"));
      return api.calculateCredit(token, creditCarId, creditTrimId, initialPercent, months);
    },
    onSuccess: setMonthlyResult,
  });
  const leadMutation = useMutation({
    mutationFn: (payload: LeadPayload) => api.createLead(token, payload),
    onSuccess: () => {
      hapticSuccess();
      setRequestError("");
      setScreen("success");
      void queryClient.invalidateQueries({ queryKey: ["favorites", token] });
    },
    onError: (error: unknown) => setRequestError(error instanceof Error ? error.message : t("unavailable")),
  });
  const [initialPercent, setInitialPercent] = useState(30);
  const [months, setMonths] = useState(36);

  function navigate(next: Screen) {
    hapticSelection();
    setScreen(next);
  }

  function openCar(car: Car) {
    setSelectedSlug(car.slug);
    setActiveImage(0);
    navigate("detail");
  }

  function openRequest(type: LeadType, car?: Car, trimId?: number) {
    setRequestType(type);
    setRequestCarId(car?.id ?? null);
    setRequestTrimId(trimId ?? null);
    setRequestError("");
    navigate("request");
  }

  function toggleCompare(car: Car) {
    setComparisonIds((current) => {
      if (current.includes(car.id)) return current.filter((id) => id !== car.id);
      if (current.length >= 3) return current;
      return [...current, car.id];
    });
    hapticSelection();
  }

  const back = useCallback(() => {
    if (screen === "request" && selectedCar) setScreen("detail");
    else if (screen === "credit" && selectedCar) setScreen("detail");
    else setScreen("home");
  }, [screen, selectedCar]);

  useEffect(() => {
    const button = getTelegramWebApp()?.BackButton;
    if (!button) return;
    if (screen === "home" || screen === "compare") {
      button.hide();
      return;
    }
    button.show();
    button.onClick(back);
    return () => {
      button.offClick(back);
      button.hide();
    };
  }, [back, screen]);

  useEffect(() => {
    const button = getTelegramWebApp()?.MainButton;
    if (!button) return;
    if (screen === "detail" && selectedCar) {
      button.setText(t("request"));
      const request = () => {
        hapticSelection();
        setRequestType("callback");
        setRequestCarId(selectedCar.id);
        setRequestTrimId(null);
        setRequestError("");
        setScreen("request");
      };
      button.show();
      button.onClick(request);
      return () => {
        button.offClick(request);
        button.hide();
      };
    }
    if (screen !== "request") {
      button.hide();
      return;
    }
    button.setText(t("send"));
    const submit = () => leadForm.current?.requestSubmit();
    button.show();
    button.onClick(submit);
    return () => {
      button.offClick(submit);
      button.hide();
    };
  }, [screen, selectedCar]);

  const startCredit = (car: Car, trimId?: number) => {
    setCreditCarId(car.id);
    setCreditTrimId(trimId ?? car.trims.find((trim) => trim.price !== null)?.id ?? null);
    setMonthlyResult(null);
    navigate("credit");
  };

  function submitLead(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const name = String(formData.get("name") || "").trim();
    const phone = requestPhone.replace(/\s+/g, "");
    if (name.length < 2) {
      setRequestError(t("nameRequired"));
      return;
    }
    if (!/^\+998\d{9}$/.test(phone)) {
      setRequestError(t("phoneInvalid"));
      return;
    }
    leadMutation.mutate({
      name,
      phone,
      type: requestType,
      car_id: requestCarId,
      trim_id: requestTrimId,
      comment: String(formData.get("comment") || "").trim() || null,
    });
  }

  function screenTitle() {
    if (screen === "favorites") return t("favorites");
    if (screen === "contacts") return t("contacts");
    if (screen === "compare") return t("compare");
    if (screen === "credit") return t("creditTitle");
    if (screen === "request") return t("request");
    if (screen === "success") return t("successTitle");
    return selectedCar ? carName(selectedCar) : t("home");
  }

  return (
    <main className="showroom">
      <header className="app-header">
        <button className="wordmark" onClick={() => navigate("home")} aria-label={t("home")}>
          <span className="wordmark-mark">VW</span>
          <span>{t("brand")}</span>
        </button>
      </header>

      {screen === "compare" ? (
        <div className="screen-heading compare-heading"><h1>{screenTitle()}</h1></div>
      ) : screen !== "home" && (
        <div className="screen-heading">
          <button className="back-button" onClick={back} aria-label={t("back")}>‹ {t("back")}</button>
          <h1>{screenTitle()}</h1>
        </div>
      )}

      {screen === "home" && (
        <section className="home-screen">
          <div className="intro">
            <p className="app-eyebrow">{t("eyebrow")}</p>
            <h1>{t("heroText")}</h1>
            {customerName && <p className="intro-greeting">{customerName}, {t("greeting")}</p>}
          </div>
          <label className="search-field">
            <Icon name="search" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("search")} aria-label={t("search")} />
          </label>
          {heroCars.length > 0 && (
            <HeroCarousel
              cars={heroCars}
              activeIndex={heroIndex % heroCars.length}
              onIndex={setHeroIndex}
              onOpen={openCar}
            />
          )}
          <section className="category-section" aria-label={t("categories")}>
            <div className="section-title-row"><h2>{t("categories")}</h2></div>
            <div className="category-strip">
              <CategoryButton icon="catalog" active={bodyFilter === "all"} onClick={() => setBodyFilter("all")}>{t("all")}</CategoryButton>
              <CategoryButton icon="suv" active={bodyFilter === "suv"} onClick={() => setBodyFilter(bodyFilter === "suv" ? "all" : "suv")}>{t("suv")}</CategoryButton>
              <CategoryButton icon="sedan" active={bodyFilter === "sedan"} onClick={() => setBodyFilter(bodyFilter === "sedan" ? "all" : "sedan")}>{t("sedan")}</CategoryButton>
            </div>
          </section>
          <div className="catalog-tools">
            <button className="filter-open-button" onClick={() => setFiltersOpen(true)}>
              <Icon name="filter" /> {t("filter")}
              {activeFilterCount > 0 && <span className="count-badge">{activeFilterCount}</span>}
            </button>
            <label className="budget-quick">
              <Icon name="wallet" />
              <input
                inputMode="numeric"
                value={budgetAmount}
                onChange={(event) => setBudgetAmount(event.target.value.replace(/\D/g, "").slice(0, 4))}
                placeholder={t("myBudget")}
                aria-label={`${t("myBudget")} (${t("millionSom")})`}
              />
              <span>{t("millionSom")}</span>
            </label>
            <label className="sort-control">
              <span className="visually-hidden">{t("sort")}</span>
              <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)}>
                <option value="popular">{t("popularSort")}</option>
                <option value="price_asc">{t("lowestPrice")}</option>
                <option value="price_desc">{t("highestPrice")}</option>
              </select>
            </label>
          </div>
          {(activeFilterCount > 0) && (
            <div className="filter-summary" aria-label={t("filters")}>
              {bodyFilter !== "all" && <button className="selected-chip" onClick={() => setBodyFilter("all")}>{bodyFilter === "suv" ? t("suv") : t("sedan")} ×</button>}
              {driveFilter !== "all" && <button className="selected-chip" onClick={() => setDriveFilter("all")}>{driveFilter} ×</button>}
              {engineFilter && <button className="selected-chip" onClick={() => setEngineFilter("")}>{engineFilter} ×</button>}
              {(priceMin > 0 || priceMax < sliderMax) && <button className="selected-chip" onClick={() => { setPriceMin(0); setPriceMax(sliderMax); }}>{t("budget")} ×</button>}
              {budgetAmount && <button className="selected-chip" onClick={() => setBudgetAmount("")}>{budgetAmount} {t("millionSom")} ×</button>}
              <button className="clear-filters" onClick={() => {
                setBodyFilter("all");
                setDriveFilter("all");
                setEngineFilter("");
                setPriceMin(0);
                setPriceMax(sliderMax);
                setBudgetAmount("");
              }}>{t("clearFilters")}</button>
            </div>
          )}
          <div className="catalog-heading">
            <div><p className="app-eyebrow">{t("popularCategory")}</p><h2>{t("popular")}</h2><span>{visibleCars.length} {t("modelCount")}</span></div>
            <button className="compare-link" onClick={() => navigate("compare")}>
              <Icon name="compare" /> {t("compare")}{comparisonIds.length > 0 && <span className="count-badge">{comparisonIds.length}</span>}
            </button>
          </div>
          {carsQuery.isPending ? <CarSkeletons /> : carsQuery.isError ? (
            <ErrorPanel message={t("unavailable")} onRetry={() => void carsQuery.refetch()} />
          ) : (
            <>
              {comparisonIds.length > 0 && (
                <button className="primary-button compare-cta" disabled={comparisonIds.length < 2} onClick={() => navigate("compare")}>
                  {t("compare")} · {comparisonIds.length} {t("selection")}
                </button>
              )}
              {visibleCars.length ? (
                <div className="car-grid">
                  {visibleCars.map((car) => (
                    <CarCard
                      key={car.id}
                      car={car}
                      isFavorite={favoriteIds.has(car.id)}
                      inCompare={comparisonIds.includes(car.id)}
                      compareDisabled={comparisonIds.length >= 3 && !comparisonIds.includes(car.id)}
                      onOpen={() => openCar(car)}
                      onFavorite={() => favoriteMutation.mutate({ carId: car.id, isFavorite: favoriteIds.has(car.id) })}
                      onCompare={() => toggleCompare(car)}
                    />
                  ))}
                </div>
              ) : <EmptyPanel>{t("noResults")}</EmptyPanel>}
              {unpricedCars.length > 0 && (
                <p className="unpriced-note">{t("nullPriceNote")}: {unpricedCars.map(carName).join(", ")}.</p>
              )}
              <p className="vat-note">{t("priceIncludesVat")}</p>
            </>
          )}
        </section>
      )}

      {screen === "detail" && selectedCar && (
        <CarDetail
          car={selectedCar}
          activeImage={activeImage}
          favorite={favoriteIds.has(selectedCar.id)}
          touchStart={touchStart}
          onTouchStart={setTouchStart}
          onTouchEnd={(end) => {
            if (touchStart === null) return;
            const count = selectedCar.images.length;
            if (count > 1 && end - touchStart < -40) setActiveImage((activeImage + 1) % count);
            if (count > 1 && end - touchStart > 40) setActiveImage((activeImage + count - 1) % count);
            setTouchStart(null);
          }}
          onImage={setActiveImage}
          onFavorite={() => favoriteMutation.mutate({ carId: selectedCar.id, isFavorite: favoriteIds.has(selectedCar.id) })}
          onRequest={(type, trimId) => openRequest(type, selectedCar, trimId)}
          onCredit={(trimId) => startCredit(selectedCar, trimId)}
          inCompare={comparisonIds.includes(selectedCar.id)}
          compareDisabled={comparisonIds.length >= 3 && !comparisonIds.includes(selectedCar.id)}
          onCompare={() => toggleCompare(selectedCar)}
        />
      )}

      {screen === "compare" && (
        <CompareScreen
          cars={comparisonQuery.data || []}
          selectedCount={comparisonIds.length}
          loading={comparisonQuery.isPending}
          error={comparisonQuery.isError}
          onRetry={() => void comparisonQuery.refetch()}
          onRemove={(id) => setComparisonIds((current) => current.filter((carId) => carId !== id))}
          onChoose={() => navigate("home")}
        />
      )}

      {screen === "credit" && (
        <CreditScreen
          cars={cars}
          carId={creditCarId}
          trimId={creditTrimId}
          setCarId={(id) => {
            setCreditCarId(id);
            setCreditTrimId(cars.find((car) => car.id === id)?.trims.find((trim) => trim.price !== null)?.id ?? null);
            setMonthlyResult(null);
          }}
          setTrimId={(id) => { setCreditTrimId(id); setMonthlyResult(null); }}
          initialPercent={initialPercent}
          setInitialPercent={setInitialPercent}
          months={months}
          setMonths={setMonths}
          result={monthlyResult}
          isPending={creditMutation.isPending}
          error={creditMutation.error}
          onCalculate={() => creditMutation.mutate()}
        />
      )}

      {screen === "request" && (
        <RequestScreen
          formRef={leadForm}
          cars={cars}
          carId={requestCarId}
          trimId={requestTrimId}
          type={requestType}
          customerName={customerName}
          phone={requestPhone}
          error={requestError}
          isPending={leadMutation.isPending}
          onCar={(id) => { setRequestCarId(id); setRequestTrimId(null); }}
          onTrim={setRequestTrimId}
          onType={setRequestType}
          onPhone={(value) => {
            const digits = value.replace(/\D/g, "");
            if (!digits || digits === "998") setRequestPhone(digits ? "+998" : "");
            else if (digits.startsWith("998")) setRequestPhone(`+${digits.slice(0, 12)}`);
            else setRequestPhone(`+998${digits.slice(-9)}`);
          }}
          onSubmit={submitLead}
        />
      )}

      {screen === "success" && (
        <section className="success-panel">
          <div className="success-mark" aria-hidden="true">✓</div>
          <h2>{t("successTitle")}</h2>
          <p>{t("successText")}</p>
          <button className="primary-button" onClick={() => navigate(selectedCar ? "detail" : "home")}>{t("home")}</button>
        </section>
      )}

      {screen === "favorites" && (
        <section className="sub-screen">
          {favoriteQuery.isPending ? <CarSkeletons /> : favoriteQuery.isError ? (
            <ErrorPanel message={t("unavailable")} onRetry={() => void favoriteQuery.refetch()} />
          ) : favoriteQuery.data?.length ? (
            <div className="car-grid">{favoriteQuery.data.map((car) => (
              <CarCard
                key={car.id}
                car={car}
                isFavorite
                inCompare={comparisonIds.includes(car.id)}
                compareDisabled={comparisonIds.length >= 3 && !comparisonIds.includes(car.id)}
                onOpen={() => openCar(car)}
                onFavorite={() => favoriteMutation.mutate({ carId: car.id, isFavorite: true })}
                onCompare={() => toggleCompare(car)}
              />
            ))}</div>
          ) : <EmptyPanel>{t("noFavorites")}</EmptyPanel>}
        </section>
      )}

      {screen === "contacts" && (
        <section className="contacts-panel sub-screen">
          {contactsQuery.isPending ? <p role="status">{t("loading")}</p> : contactsQuery.isError || !contactsQuery.data ? (
            <ErrorPanel message={t("noContacts")} onRetry={() => void contactsQuery.refetch()} />
          ) : (
            <>
              <p className="app-eyebrow">{contactsQuery.data.name}</p>
              <h2>{t("address")}</h2>
              <p>{contactsQuery.data.address}</p>
              <p className="muted">{t("landmark")}</p>
              <div className="contact-lines">
                {contactsQuery.data.phones.map((phone) => <a key={phone} href={`tel:${phone}`}>{phone}</a>)}
              </div>
              {contactsQuery.data.phones[0] && (
                <a className="primary-button" href={`tel:${contactsQuery.data.phones[0]}`}>
                  <Icon name="phone" /> {t("call")}
                </a>
              )}
              {contactsQuery.data.working_hours && <p><strong>{t("workingHours")}</strong><br />{contactsQuery.data.working_hours}</p>}
              <a className="contact-link" href={`https://instagram.com/${contactsQuery.data.instagram.replace(/^@/, "")}`} target="_blank" rel="noreferrer">{t("instagram")} · @{contactsQuery.data.instagram.replace(/^@/, "")}</a>
              {contactsQuery.data.telegram_url && <a className="contact-link" href={contactsQuery.data.telegram_url} target="_blank" rel="noreferrer"><Icon name="telegram" /> {t("telegram")}</a>}
              {contactsQuery.data.map_link && <a className="secondary-button" href={contactsQuery.data.map_link} target="_blank" rel="noreferrer"><Icon name="pin" /> {t("route")}</a>}
            </>
          )}
        </section>
      )}

      {filtersOpen && (
        <div className="sheet-backdrop" onClick={() => setFiltersOpen(false)}>
          <section
            className="filter-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="filter-sheet-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="sheet-header">
              <h2 id="filter-sheet-title">{t("filters")}</h2>
              <button className="icon-button" onClick={() => setFiltersOpen(false)} aria-label={t("close")}><Icon name="close" /></button>
            </header>
            <fieldset className="sheet-fieldset">
              <legend>{t("categories")}</legend>
              <div className="sheet-options">
                {([
                  ["all", t("all")],
                  ["suv", t("suv")],
                  ["sedan", t("sedan")],
                ] as const).map(([value, label]) => (
                  <button className={`filter-chip ${bodyFilter === value ? "filter-chip-active" : ""}`} key={value} onClick={() => setBodyFilter(value)} aria-pressed={bodyFilter === value}>{label}</button>
                ))}
              </div>
            </fieldset>
            <fieldset className="sheet-fieldset">
              <legend>{t("drive")}</legend>
              <div className="sheet-options">
                {(["all", "AWD", "FWD"] as const).map((value) => (
                  <button className={`filter-chip ${driveFilter === value ? "filter-chip-active" : ""}`} key={value} onClick={() => setDriveFilter(value)} aria-pressed={driveFilter === value}>{value === "all" ? t("all") : value}</button>
                ))}
              </div>
            </fieldset>
            <fieldset className="sheet-fieldset">
              <legend>{t("budget")}</legend>
              <div className="range-control">
                <label>{t("minimumPrice")} <strong>{Math.round(priceMin / PRICE_MILLION)} mln</strong></label>
                <input type="range" min="0" max={sliderMax} step={25 * PRICE_MILLION} value={priceMin} onChange={(event) => setPriceMin(Math.min(Number(event.target.value), priceMax))} />
                <label>{t("maximumPrice")} <strong>{Math.round(priceMax / PRICE_MILLION)} mln</strong></label>
                <input type="range" min="0" max={sliderMax} step={25 * PRICE_MILLION} value={priceMax} onChange={(event) => setPriceMax(Math.max(Number(event.target.value), priceMin))} />
                <div className="range-labels"><span>0 mln</span><span>{Math.round(sliderMax / PRICE_MILLION)} mln so'm</span></div>
              </div>
            </fieldset>
            <label className="sheet-fieldset engine-field">
              <span>{t("engineFilter")}</span>
              <input value={engineFilter} onChange={(event) => setEngineFilter(event.target.value)} placeholder="Masalan, 2.0 TSI" />
            </label>
            <div className="sheet-actions">
              <button className="secondary-button" onClick={() => {
                setBodyFilter("all");
                setDriveFilter("all");
                setEngineFilter("");
                setPriceMin(0);
                setPriceMax(sliderMax);
                setBudgetAmount("");
              }}>{t("clearFilters")}</button>
              <button className="primary-button" onClick={() => setFiltersOpen(false)}>{t("applyFilters")} · {visibleCars.length}</button>
            </div>
          </section>
        </div>
      )}

      <nav className="bottom-nav" aria-label="Asosiy menyu">
        <NavButton active={screen === "home" || screen === "detail" || screen === "request" || screen === "success"} icon="catalog" label={t("home")} onClick={() => navigate("home")} />
        <NavButton active={screen === "compare"} icon="compare" label={t("compare")} badge={comparisonIds.length} onClick={() => navigate("compare")} />
        <NavButton active={screen === "credit"} icon="credit" label={t("credit")} onClick={() => navigate("credit")} />
        <NavButton active={screen === "favorites"} icon="heart" label={t("favorites")} onClick={() => navigate("favorites")} />
        <NavButton active={screen === "contacts"} icon="pin" label={t("contacts")} onClick={() => navigate("contacts")} />
      </nav>
    </main>
  );
}

type IconName = "search" | "filter" | "wallet" | "catalog" | "suv" | "sedan" | "compare" | "check" | "credit" | "heart" | "pin" | "phone" | "telegram" | "close" | "chevron";

function Icon({ name, filled = false }: { name: IconName; filled?: boolean }) {
  const paths: Record<IconName, string> = {
    search: "M20 20l-4.5-4.5M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z",
    filter: "M4 6h16M7 12h10m-7 6h4",
    wallet: "M4 6.5A2.5 2.5 0 0 1 6.5 4H20v16H6.5A2.5 2.5 0 0 1 4 17.5v-11ZM4 7h16m-5 5h.01",
    catalog: "M3 11.5 12 4l9 7.5M5.5 10v10h13V10M9 20v-6h6v6",
    suv: "M3 15v-3l2-5h12l4 5v3h-2m-12 0h8m-8 0a2 2 0 1 0 4 0m4 0a2 2 0 1 0 4 0M6 7l1.5 5h9",
    sedan: "M3 15v-3l3-4h10l4 4v3h-2m-12 0h8m-8 0a2 2 0 1 0 4 0m4 0a2 2 0 1 0 4 0M7 8l1 4h8l-1-4",
    compare: "M8 5H5a2 2 0 0 0-2 2v12h12v-3M9 3h12v12H9zM12 7h6m-6 4h6",
    check: "m5 12 4 4L19 6",
    credit: "M3 7h18v12H3zM3 10h18m-14 5h4m-7-8 3-4h13v4",
    heart: "M20.8 8.8c0 5.2-8.8 11-8.8 11s-8.8-5.8-8.8-11A4.8 4.8 0 0 1 12 6.1a4.8 4.8 0 0 1 8.8 2.7Z",
    pin: "M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Zm-5 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
    phone: "M7 3H4a1 1 0 0 0-1 1c0 9.4 7.6 17 17 17a1 1 0 0 0 1-1v-3l-5-2-2 3a14 14 0 0 1-7-7l3-2-2-5Z",
    telegram: "m21 4-4 17-6-5-3 3v-5l9-8-12 7-4-1 20-8Z",
    close: "m6 6 12 12M18 6 6 18",
    chevron: "m9 18 6-6-6-6",
  };
  return (
    <svg
      aria-hidden="true"
      className="icon"
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
    >
      <path d={paths[name]} />
    </svg>
  );
}

function CategoryButton({
  icon,
  active,
  children,
  onClick,
}: {
  icon: IconName;
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button className={`category-button ${active ? "category-button-active" : ""}`} onClick={onClick} aria-pressed={active}>
      <span className="category-icon"><Icon name={icon} /></span>
      <span>{children}</span>
    </button>
  );
}

function NavButton({
  active,
  icon,
  label,
  badge,
  onClick,
}: {
  active: boolean;
  icon: IconName;
  label: string;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <button className={`bottom-nav-item ${active ? "bottom-nav-active" : ""}`} onClick={onClick} aria-current={active ? "page" : undefined}>
      <span className="nav-icon-wrap"><Icon name={icon} filled={icon === "heart" && active} />{badge ? <small>{badge}</small> : null}</span>
      <span>{label}</span>
    </button>
  );
}

function HeroCarousel({
  cars,
  activeIndex,
  onIndex,
  onOpen,
}: {
  cars: Car[];
  activeIndex: number;
  onIndex: (index: number) => void;
  onOpen: (car: Car) => void;
}) {
  const car = cars[activeIndex];
  const image = car ? imageFor(car) : undefined;
  const [imageFailed, setImageFailed] = useState(false);
  const [paused, setPaused] = useState(false);
  const touchStart = useRef<number | null>(null);
  useEffect(() => setImageFailed(false), [image]);
  useEffect(() => {
    if (paused || cars.length < 2) return;
    const timer = window.setInterval(
      () => onIndex((activeIndex + 1) % cars.length),
      5000,
    );
    return () => window.clearInterval(timer);
  }, [activeIndex, cars.length, onIndex, paused]);
  if (!car) return null;
  const next = (step: number) => onIndex((activeIndex + step + cars.length) % cars.length);
  return (
    <section
      className="hero-carousel"
      aria-label={t("heroEyebrow")}
      onPointerDown={() => setPaused(true)}
      onKeyDown={() => setPaused(true)}
      onTouchStart={(event) => {
        touchStart.current = event.touches[0]?.clientX ?? null;
        setPaused(true);
      }}
      onTouchEnd={(event) => {
        const start = touchStart.current;
        touchStart.current = null;
        if (start === null) return;
        const distance = event.changedTouches[0].clientX - start;
        if (distance < -40) next(1);
        else if (distance > 40) next(-1);
      }}
    >
      {image && !imageFailed ? <img className="hero-image" src={image} alt="" loading="lazy" onError={() => setImageFailed(true)} /> : <div className="hero-art" aria-hidden="true"><span>VW</span></div>}
      <div className="hero-shade" />
      <div className="hero-content">
        <p>{t("heroEyebrow")}</p>
        <h2>{carName(car)}</h2>
        <span>{priceRange(car)}</span>
        <button className="hero-action" onClick={() => onOpen(car)}>{t("heroAction")} <Icon name="chevron" /></button>
      </div>
      <div className="hero-controls">
        <div className="hero-dots">
          {cars.map((item, index) => <button key={item.id} className={index === activeIndex ? "hero-dot hero-dot-active" : "hero-dot"} onClick={() => onIndex(index)} aria-label={`${t("heroAction")}: ${carName(item)}`} />)}
        </div>
      </div>
    </section>
  );
}

function CarPlaceholder({ car, className = "" }: { car: Car; className?: string }) {
  return (
    <div className={`image-placeholder ${className}`}>
      <span>{car.brand}</span>
      <strong>{car.model}</strong>
    </div>
  );
}

function CarCard({
  car,
  isFavorite,
  inCompare,
  compareDisabled,
  onOpen,
  onFavorite,
  onCompare,
}: {
  car: Car;
  isFavorite: boolean;
  inCompare: boolean;
  compareDisabled: boolean;
  onOpen: () => void;
  onFavorite: () => void;
  onCompare: () => void;
}) {
  const src = imageFor(car);
  const starting = lowestPrice(car);
  const [imageFailed, setImageFailed] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  useEffect(() => {
    setImageFailed(false);
    setImageLoaded(false);
  }, [src]);
  return (
    <article className="car-card">
      <button className="car-card-main" onClick={onOpen} aria-label={`${carName(car)} — ${t("details")}`}>
        <div className="car-image-wrap">
          {src && !imageFailed ? (
            <>
              <img src={src} alt={carName(car)} loading="lazy" decoding="async" onLoad={() => setImageLoaded(true)} onError={() => setImageFailed(true)} />
              {!imageLoaded && <span className="car-image-skeleton" aria-hidden="true" />}
            </>
          ) : <CarPlaceholder car={car} />}
          <span className="body-label">{car.body_type}</span>
        </div>
        <div className="car-card-content">
          <h3>{carName(car)}</h3>
          <p className="car-card-specs">{car.engine} <span>·</span> {car.drive.toUpperCase().includes("AWD") ? "AWD" : "FWD"}</p>
          <span className="price-label">{starting === null ? t("laterPrice") : `${priceText(starting)} ${t("startingAt")}`}</span>
        </div>
      </button>
      <div className="card-actions">
        <button className={`icon-button ${isFavorite ? "icon-active" : ""}`} onClick={onFavorite} aria-pressed={isFavorite} aria-label={isFavorite ? t("removeFavorite") : t("addFavorite")}><Icon name="heart" filled={isFavorite} /></button>
        <button className={`compare-toggle ${inCompare ? "compare-toggle-active" : ""}`} disabled={compareDisabled} onClick={onCompare} role="checkbox" aria-checked={inCompare} aria-label={inCompare ? t("compareRemove") : t("compareSelected")}><Icon name={inCompare ? "check" : "compare"} /></button>
      </div>
    </article>
  );
}

function CarSkeletons() {
  return <div className="car-grid" aria-label={t("loading")}>{[1, 2, 3].map((item) => <div className="skeleton-card" key={item}><div className="skeleton-image" /><div className="skeleton-line" /><div className="skeleton-line skeleton-short" /></div>)}</div>;
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="state-card state-error" role="alert"><p>{message}</p><button className="secondary-button" onClick={onRetry}>{t("retry")}</button></div>;
}

function EmptyPanel({ children }: { children: string }) {
  return <div className="empty-panel">{children}</div>;
}

function CarDetail({
  car,
  activeImage,
  favorite,
  touchStart,
  onTouchStart,
  onTouchEnd,
  onImage,
  onFavorite,
  onRequest,
  onCredit,
  inCompare,
  compareDisabled,
  onCompare,
}: {
  car: Car;
  activeImage: number;
  favorite: boolean;
  touchStart: number | null;
  onTouchStart: (value: number) => void;
  onTouchEnd: (value: number) => void;
  onImage: (index: number) => void;
  onFavorite: () => void;
  onRequest: (type: LeadType, trimId?: number) => void;
  onCredit: (trimId?: number) => void;
  inCompare: boolean;
  compareDisabled: boolean;
  onCompare: () => void;
}) {
  const images = [...car.images].sort((a, b) => a.sort_order - b.sort_order);
  const active = images[activeImage];
  const activeSrc = api.imageUrl(active?.path || car.image_url);
  const [imageFailed, setImageFailed] = useState(false);
  useEffect(() => setImageFailed(false), [activeSrc]);
  return (
    <section className="detail-screen">
      <div
        className="detail-gallery"
        onTouchStart={(event) => onTouchStart(event.touches[0].clientX)}
        onTouchEnd={(event) => touchStart !== null && onTouchEnd(event.changedTouches[0].clientX)}
      >
        {activeSrc && !imageFailed ? <img className="detail-image" src={activeSrc} srcSet={active?.thumbnail_path && active.path ? `${api.imageUrl(active.thumbnail_path)} 480w, ${api.imageUrl(active.path)} 1920w` : undefined} sizes="100vw" loading="lazy" decoding="async" onError={() => setImageFailed(true)} alt={`${carName(car)} ${activeImage + 1}`} /> : <CarPlaceholder car={car} className="detail-placeholder" />}
        <button className={`detail-favorite ${favorite ? "icon-active" : ""}`} onClick={onFavorite} aria-pressed={favorite} aria-label={favorite ? t("removeFavorite") : t("addFavorite")}><Icon name="heart" filled={favorite} /></button>
        <span className="gallery-counter">{images.length ? `${activeImage + 1} / ${images.length}` : "—"}</span>
      </div>
      {images.length > 1 && <div className="thumbnail-row">{images.map((image, index) => {
        const src = api.imageUrl(image.thumbnail_path || image.path);
        return <button className={`thumbnail ${activeImage === index ? "thumbnail-active" : ""}`} key={image.id} onClick={() => onImage(index)} aria-label={`${carName(car)} rasmi ${index + 1}`}><img src={src} alt="" loading="lazy" /></button>;
      })}</div>}
      <div className="detail-title">
        <div><p className="app-eyebrow">{car.body_type}</p><h1>{carName(car)}</h1><p className="muted">{t("startingAt")} {priceRange(car)}</p></div>
      </div>
      <section className="detail-section">
        <h2>{t("specs")}</h2>
        <dl className="spec-grid">
          <Spec label={t("engine")} value={car.engine} />
          <Spec label={t("power")} value={`${car.power_hp} o.k.`} />
          <Spec label={t("emission")} value={car.emission} />
          <Spec label={t("drive")} value={car.drive} />
          <Spec label={t("transmission")} value={car.transmission} />
          <Spec label={t("seats")} value={`${car.seats}`} />
        </dl>
      </section>
      <section className="detail-section">
        <h2>{t("trims")}</h2>
        <div className="trim-list">{car.trims.map((trim) => (
          <article className="trim-row" key={trim.id}>
            <div><strong>{trim.name}</strong><span>{priceText(trim.price)}</span></div>
            {trim.price !== null && <button className="small-link" onClick={() => onCredit(trim.id)}>{t("credit")}</button>}
          </article>
        ))}</div>
      </section>
      <div className="detail-actions">
        <button className="primary-button" onClick={() => onRequest("test_drive")}>{t("testDrive")}</button>
        <button className="secondary-button" onClick={() => onRequest("buy")}>{t("buy")}</button>
        <button className="secondary-button" onClick={() => onCredit()}><Icon name="credit" /> {t("credit")}</button>
        <button className="secondary-button" disabled={compareDisabled} aria-pressed={inCompare} onClick={onCompare}><Icon name="compare" /> {inCompare ? t("compareRemove") : t("compareSelected")}</button>
      </div>
    </section>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  return <div className="spec-item"><dt>{label}</dt><dd>{value}</dd></div>;
}

function CompareScreen({
  cars,
  selectedCount,
  loading,
  error,
  onRetry,
  onRemove,
  onChoose,
}: {
  cars: Car[];
  selectedCount: number;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  onRemove: (id: number) => void;
  onChoose: () => void;
}) {
  if (selectedCount < 2) {
    return (
      <section className="compare-empty-screen">
        <span className="compare-empty-icon"><Icon name="compare" /></span>
        <p>{t("compareMinimum")}</p>
        <button className="primary-button" onClick={onChoose}>{t("goToCatalog")}</button>
      </section>
    );
  }
  if (loading) return <section className="sub-screen"><p role="status">{t("loading")}</p></section>;
  if (error) return <section className="sub-screen"><ErrorPanel message={t("unavailable")} onRetry={onRetry} /></section>;
  const rows: { label: string; get: (car: Car) => string }[] = [
    { label: t("engine"), get: (car) => car.engine },
    { label: t("power"), get: (car) => `${car.power_hp} o.k.` },
    { label: t("drive"), get: (car) => car.drive },
    { label: t("transmission"), get: (car) => car.transmission },
    { label: t("seats"), get: (car) => `${car.seats}` },
    { label: t("amount"), get: priceRange },
  ];
  return (
    <section className="sub-screen">
      <p className="muted">{t("compareLimit")}</p>
      {!cars.length ? <EmptyPanel>{t("compareEmpty")}</EmptyPanel> : (
        <div className="comparison-table">
          <div className="compare-row compare-head"><span /><div className="compare-values">{cars.map((car) => <div key={car.id}><strong>{carName(car)}</strong><button className="small-link" onClick={() => onRemove(car.id)}>{t("compareRemove")}</button></div>)}</div></div>
          {rows.map((row) => {
            const values = cars.map(row.get);
            const differs = new Set(values).size > 1;
            return <div className="compare-row" key={row.label}><strong>{row.label}</strong><div className="compare-values">{values.map((value, index) => <span className={differs ? "compare-different" : ""} key={`${cars[index].id}-${row.label}`}>{value}</span>)}</div></div>;
          })}
        </div>
      )}
      {selectedCount < 3 && <button className="secondary-button" onClick={onChoose}>{t("chooseCar")}</button>}
    </section>
  );
}

function CreditScreen({
  cars,
  carId,
  trimId,
  setCarId,
  setTrimId,
  initialPercent,
  setInitialPercent,
  months,
  setMonths,
  result,
  isPending,
  error,
  onCalculate,
}: {
  cars: Car[];
  carId: number | null;
  trimId: number | null;
  setCarId: (id: number) => void;
  setTrimId: (id: number) => void;
  initialPercent: number;
  setInitialPercent: (value: number) => void;
  months: number;
  setMonths: (value: number) => void;
  result: CreditResult | null;
  isPending: boolean;
  error: unknown;
  onCalculate: () => void;
}) {
  const car = cars.find((item) => item.id === carId);
  const pricedTrims = car?.trims.filter((trim) => trim.price !== null) || [];
  const liveResult = result ? estimateCredit(result, initialPercent, months) : null;
  return (
    <section className="calculator-panel sub-screen">
      <label>{t("car")}<select value={carId ?? ""} onChange={(event) => setCarId(Number(event.target.value))}><option value="">{t("chooseCar")}</option>{cars.map((item) => <option value={item.id} key={item.id}>{carName(item)}</option>)}</select></label>
      <label>{t("chooseTrim")}<select value={trimId ?? ""} onChange={(event) => setTrimId(Number(event.target.value))} disabled={!pricedTrims.length}><option value="">{t("chooseTrim")}</option>{pricedTrims.map((trim) => <option value={trim.id} key={trim.id}>{trim.name} — {priceText(trim.price)}</option>)}</select></label>
      <div className="calculator-field">
        <div className="field-heading"><label htmlFor="initial-payment">{t("initialPayment")}</label><strong>{initialPercent}%</strong></div>
        <input id="initial-payment" type="range" min="20" max="50" step="10" value={initialPercent} onChange={(event) => setInitialPercent(Number(event.target.value))} />
        <div className="range-labels"><span>20%</span><span>50%</span></div>
      </div>
      <label>{t("term")}<select value={months} onChange={(event) => setMonths(Number(event.target.value))}>{[12, 24, 36, 48, 60].map((value) => <option key={value} value={value}>{value} oy</option>)}</select></label>
      <button className="primary-button" disabled={!carId || !trimId || isPending} onClick={onCalculate}>{isPending ? t("loading") : t("calculate")}</button>
      {error instanceof Error && <p className="form-error" role="alert">{error.message}</p>}
      {liveResult && (
        <div className="credit-result">
          <p className="app-eyebrow">{t("monthlyPayment")}</p>
          <strong>{priceText(liveResult.monthly_payment)}</strong>
          <dl>
            <dt>{t("amount")}</dt><dd>{priceText(liveResult.amount)}</dd>
            <dt>{t("initialPayment")}</dt><dd>{priceText(liveResult.initial_payment)}</dd>
            <dt>{t("term")}</dt><dd>{liveResult.months} oy</dd>
            <dt>{t("totalPayment")}</dt><dd>{priceText(liveResult.initial_payment + liveResult.monthly_payment * liveResult.months)}</dd>
          </dl>
          <p className="disclaimer">{liveResult.disclaimer}</p>
          <p className="muted">{t("approximateRate")}: {liveResult.annual_rate}%</p>
        </div>
      )}
      {!liveResult && <p className="disclaimer">{t("disclaimer")}</p>}
    </section>
  );
}

function RequestScreen({
  formRef,
  cars,
  carId,
  trimId,
  type,
  customerName,
  phone,
  error,
  isPending,
  onCar,
  onTrim,
  onType,
  onPhone,
  onSubmit,
}: {
  formRef: Ref<HTMLFormElement>;
  cars: Car[];
  carId: number | null;
  trimId: number | null;
  type: LeadType;
  customerName: string;
  phone: string;
  error: string;
  isPending: boolean;
  onCar: (id: number | null) => void;
  onTrim: (id: number | null) => void;
  onType: (type: LeadType) => void;
  onPhone: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const car = cars.find((item) => item.id === carId);
  return (
    <form className="request-form sub-screen" ref={formRef} onSubmit={onSubmit}>
      <label>{t("leadType")}<select value={type} onChange={(event) => onType(event.target.value as LeadType)}><option value="test_drive">{t("testDrive")}</option><option value="buy">{t("buy")}</option><option value="callback">{t("callback")}</option></select></label>
      <label>{t("car")}<select value={carId ?? ""} onChange={(event) => onCar(event.target.value ? Number(event.target.value) : null)}><option value="">{t("chooseCar")}</option>{cars.map((item) => <option key={item.id} value={item.id}>{carName(item)}</option>)}</select></label>
      <label>{t("chooseTrim")}<select value={trimId ?? ""} onChange={(event) => onTrim(event.target.value ? Number(event.target.value) : null)} disabled={!car}><option value="">{t("chooseTrim")}</option>{car?.trims.map((trim) => <option value={trim.id} key={trim.id}>{trim.name} · {priceText(trim.price)}</option>)}</select></label>
      <label>{t("name")}<input name="name" required minLength={2} maxLength={120} defaultValue={customerName} autoComplete="name" /></label>
      <label>{t("phone")}<input type="tel" inputMode="tel" required placeholder="+998 90 123 45 67" value={phone} onChange={(event) => onPhone(event.target.value)} autoComplete="tel" /></label>
      <label>{t("comment")}<textarea name="comment" rows={3} maxLength={2000} /></label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" disabled={isPending}>{isPending ? t("sending") : t("send")}</button>
      <p className="muted">{t("contactManager")}</p>
    </form>
  );
}

export default App;
