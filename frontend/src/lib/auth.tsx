"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { api, rotateRefreshToken } from "@/lib/api/client";
import type { AuthUserResponse } from "@/lib/api/types";

interface AuthContextValue {
  user: AuthUserResponse | null;
  loading: boolean;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [user, setUser] = useState<AuthUserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const inFlight = useRef<Promise<AuthUserResponse | null> | null>(null);

  const loadUser = useCallback((): Promise<AuthUserResponse | null> => {
    if (inFlight.current) {
      return inFlight.current;
    }
    const run = async (): Promise<AuthUserResponse | null> => {
      try {
        return await api.get<AuthUserResponse>("/users/me");
      } catch {
        return null;
      }
    };
    inFlight.current = run().finally(() => {
      inFlight.current = null;
    });
    return inFlight.current;
  }, []);

  useEffect(() => {
    void loadUser().then((loaded) => {
      setUser(loaded);
      setLoading(false);
    });
  }, [loadUser]);

  const reload = useCallback(async () => {
    const loaded = await loadUser();
    setUser(loaded);
  }, [loadUser]);

  const logout = useCallback(async () => {
    await api.post("/auth/logout").catch(() => undefined);
    await rotateRefreshToken();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, logout, reload }),
    [user, loading, logout, reload],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}