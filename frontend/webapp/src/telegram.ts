export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
}

interface TelegramButton {
  setText(text: string): void;
  show(): void;
  hide(): void;
  enable(): void;
  disable(): void;
  showProgress(leaveActive?: boolean): void;
  hideProgress(): void;
  onClick(callback: () => void): void;
  offClick(callback: () => void): void;
}

interface TelegramBackButton {
  show(): void;
  hide(): void;
  onClick(callback: () => void): void;
  offClick(callback: () => void): void;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: TelegramUser };
  colorScheme: "light" | "dark";
  themeParams: Record<string, string | undefined>;
  MainButton: TelegramButton;
  BackButton: TelegramBackButton;
  ready(): void;
  expand(): void;
  setHeaderColor?(color: string): void;
  setBackgroundColor?(color: string): void;
  onEvent?(eventType: "themeChanged", eventHandler: () => void): void;
  offEvent?(eventType: "themeChanged", eventHandler: () => void): void;
  requestContact?(callback: (shared: boolean) => void): void;
  HapticFeedback?: {
    impactOccurred(style: "light" | "medium" | "heavy"): void;
    notificationOccurred(type: "error" | "success" | "warning"): void;
    selectionChanged(): void;
  };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getTelegramWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

export function prepareTelegramWebApp(): TelegramWebApp | undefined {
  const webApp = getTelegramWebApp();
  if (!webApp) return undefined;

  webApp.ready();
  webApp.expand();

  const colorVariables: Record<string, string> = {
    bg_color: "--tg-bg",
    secondary_bg_color: "--tg-secondary-bg",
    text_color: "--tg-text",
    hint_color: "--tg-hint",
    button_color: "--tg-button",
    button_text_color: "--tg-button-text",
  };

  const applyTheme = () => {
    document.documentElement.dataset.theme = webApp.colorScheme;
    for (const [parameter, variable] of Object.entries(colorVariables)) {
      const color = webApp.themeParams[parameter];
      if (color && /^#[\da-f]{6}$/i.test(color)) {
        document.documentElement.style.setProperty(variable, color);
      }
    }
    const pageBackground = getComputedStyle(document.documentElement)
      .getPropertyValue("--page")
      .trim();
    const fallbackBackground = webApp.colorScheme === "dark" ? "#15161a" : "#f7f8fa";
    webApp.setBackgroundColor?.(
      /^#[\da-f]{6}$/i.test(pageBackground) ? pageBackground : fallbackBackground,
    );
    webApp.setHeaderColor?.("#001E50");
  };
  applyTheme();
  webApp.onEvent?.("themeChanged", applyTheme);
  return webApp;
}

export function hapticSelection(): void {
  getTelegramWebApp()?.HapticFeedback?.selectionChanged();
}

export function hapticSuccess(): void {
  getTelegramWebApp()?.HapticFeedback?.notificationOccurred("success");
}
