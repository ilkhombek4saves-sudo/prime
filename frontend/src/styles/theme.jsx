import React, { createContext, useContext, useMemo, useState } from "react";
import { createTheme } from "@mui/material";

const ColorModeContext = createContext({
  mode: "light",
  toggleMode: () => {},
});

export function ColorModeProvider({ children }) {
  const [mode, setMode] = useState(localStorage.getItem("theme") || "light");

  const value = useMemo(
    () => ({
      mode,
      toggleMode: () => {
        const next = mode === "light" ? "dark" : "light";
        localStorage.setItem("theme", next);
        setMode(next);
      },
    }),
    [mode]
  );

  return <ColorModeContext.Provider value={value}>{children}</ColorModeContext.Provider>;
}

export function useColorModeTheme() {
  const { mode } = useContext(ColorModeContext);
  return useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          primary: { main: "#1769aa" },
          secondary: { main: "#ff7043" },
        },
      }),
    [mode]
  );
}

export function useColorMode() {
  return useContext(ColorModeContext);
}
