import { useState, useCallback } from "react";
import { api } from "./api";
import { usePolling } from "./hooks/usePolling";
import { Header }      from "./components/Header";
import { DashboardTab } from "./components/DashboardTab";
import { SignalsTab }   from "./components/SignalsTab";
import { NewsTab }      from "./components/NewsTab";
import { TweetsTab }    from "./components/TweetsTab";
import { JournalTab }   from "./components/JournalTab";
import { SettingsTab }  from "./components/SettingsTab";

const TABS = [
  { id: "dashboard", label: "Dashboard",  icon: "⬡",  component: DashboardTab },
  { id: "signals",   label: "Signals",    icon: "⚡",  component: SignalsTab },
  { id: "news",      label: "News",       icon: "📰", component: NewsTab },
  { id: "tweets",    label: "Tweets",     icon: "🐦", component: TweetsTab },
  { id: "journal",   label: "Journal",    icon: "📒", component: JournalTab },
  { id: "settings",  label: "Settings",   icon: "⚙️",  component: SettingsTab },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const { data: health, refetch: refetchHealth } = usePolling(
    useCallback(() => api.health(), []), 8000
  );

  const ActiveComponent = TABS.find(t => t.id === activeTab)?.component ?? DashboardTab;

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      <Header health={health} onKillSwitch={refetchHealth} />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-52 flex-shrink-0 border-r border-gray-800 bg-gray-950/80 flex flex-col py-4">
          <nav className="flex-1 px-3 space-y-1">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all text-left ${
                  activeTab === tab.id
                    ? "bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 font-semibold"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/60 border border-transparent"
                }`}
              >
                <span className="text-base w-5 text-center">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>

          {/* Bottom: connection info */}
          <div className="px-4 py-3 border-t border-gray-800">
            <p className="text-gray-600 text-xs truncate">
              {import.meta.env.VITE_API_URL || "localhost:8000"}
            </p>
            <p className="text-gray-700 text-xs mt-0.5">XAU/USD only</p>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <ActiveComponent />
        </main>
      </div>
    </div>
  );
}
