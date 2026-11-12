import { create } from "zustand";

interface AgentStore {
    isRunning: boolean;
    status: string;
    setIsRunning: (isRunning: boolean) => void;
    setStatus: (status: string) => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
    isRunning: false,
    status: "Agent is not running",
    setIsRunning: (isRunning: boolean) => set({ isRunning }),
    setStatus: (status: string) => set({ status }),
}));