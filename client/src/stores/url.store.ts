import { create } from "zustand";

interface UrlStore {
    currentUrl: string;
    pageName: string;
    setCurrentUrl: (url: string, pageName: string) => void;
}

export const useUrlStore = create<UrlStore>((set) => ({
    currentUrl: window.location.hash,
    pageName: "",
    setCurrentUrl: (url: string, pageName: string) => set({ currentUrl: url, pageName }),
}));
