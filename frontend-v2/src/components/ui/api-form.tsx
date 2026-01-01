import * as React from "react";
import { createContext, useContext, useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

// Types
type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

type TabValue = "form" | "code";

interface ApiFormContextValue {
  method: HttpMethod;
  endpoint: string;
  body: Record<string, unknown>;
  onBodyChange?: (body: Record<string, unknown>) => void;
  activeTab: TabValue;
  setActiveTab: (tab: TabValue) => void;
}

const ApiFormContext = createContext<ApiFormContextValue | null>(null);

function useApiFormContext() {
  const context = useContext(ApiFormContext);
  if (!context) {
    throw new Error("ApiForm compound components must be used within ApiForm");
  }
  return context;
}

// Method color mapping
const methodColors: Record<HttpMethod, string> = {
  GET: "text-blue-400",
  POST: "text-emerald-400",
  PUT: "text-orange-400",
  DELETE: "text-red-400",
  PATCH: "text-yellow-400",
};

// Root component
interface ApiFormProps {
  method: HttpMethod;
  endpoint: string;
  body: Record<string, unknown>;
  onBodyChange?: (body: Record<string, unknown>) => void;
  defaultTab?: "form" | "code";
  children: React.ReactNode;
  className?: string;
}

function ApiForm({
  method,
  endpoint,
  body,
  onBodyChange,
  defaultTab = "form",
  children,
  className,
}: ApiFormProps) {
  const [activeTab, setActiveTab] = useState(defaultTab);

  return (
    <ApiFormContext.Provider
      value={{
        method,
        endpoint,
        body,
        onBodyChange,
        activeTab,
        setActiveTab,
      }}
    >
      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as TabValue)}
        className={cn("w-full", className)}
      >
        {children}
      </Tabs>
    </ApiFormContext.Provider>
  );
}

// Toggle sub-component
interface ToggleProps {
  className?: string;
}

function Toggle({ className }: ToggleProps) {
  return (
    <TabsList className={cn("w-full", className)}>
      <TabsTrigger value="form" className="flex-1">
        Form
      </TabsTrigger>
      <TabsTrigger value="code" className="flex-1">
        Code
      </TabsTrigger>
    </TabsList>
  );
}

// FormView sub-component
interface FormViewProps {
  children: React.ReactNode;
  className?: string;
}

function FormView({ children, className }: FormViewProps) {
  return (
    <TabsContent value="form" className={cn("py-4", className)}>
      {children}
    </TabsContent>
  );
}

// Helper to render JSON with editable inputs
interface JsonValueProps {
  keyName: string;
  value: unknown;
  path: string[];
  editable: boolean;
  onValueChange: (path: string[], value: unknown) => void;
  indent: number;
}

function JsonValue({
  keyName,
  value,
  path,
  editable,
  onValueChange,
  indent,
}: JsonValueProps) {
  const indentClass = `pl-${indent * 4}`;

  if (value === null) {
    return (
      <div className={indentClass}>
        <span className="text-sky-400">"{keyName}"</span>
        <span className="text-zinc-100">: </span>
        <span className="text-zinc-500">null</span>
      </div>
    );
  }

  if (typeof value === "boolean") {
    return (
      <div className={cn("flex items-center", indentClass)}>
        <span className="text-sky-400">"{keyName}"</span>
        <span className="text-zinc-100">:&nbsp;</span>
        {editable ? (
          <button
            type="button"
            onClick={() => onValueChange(path, !value)}
            className="text-amber-400 hover:text-amber-300 underline underline-offset-2"
          >
            {value.toString()}
          </button>
        ) : (
          <span className="text-amber-400">{value.toString()}</span>
        )}
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div className={cn("flex items-center", indentClass)}>
        <span className="text-sky-400">"{keyName}"</span>
        <span className="text-zinc-100">:&nbsp;</span>
        {editable ? (
          <input
            type="number"
            value={value}
            onChange={(e) => {
              const parsed = parseFloat(e.target.value);
              if (!isNaN(parsed)) {
                onValueChange(path, parsed);
              }
            }}
            className="w-20 bg-zinc-800 text-amber-400 border border-zinc-700 rounded px-1.5 py-0.5 text-xs font-mono focus:outline-none focus:border-emerald-500"
          />
        ) : (
          <span className="text-amber-400">{value}</span>
        )}
      </div>
    );
  }

  if (typeof value === "string") {
    return (
      <div className={cn("flex items-center", indentClass)}>
        <span className="text-sky-400">"{keyName}"</span>
        <span className="text-zinc-100">:&nbsp;</span>
        {editable ? (
          <>
            <span className="text-emerald-400">"</span>
            <input
              type="text"
              value={value}
              onChange={(e) => onValueChange(path, e.target.value)}
              className="bg-zinc-800 text-emerald-400 border border-zinc-700 rounded px-1.5 py-0.5 text-xs font-mono focus:outline-none focus:border-emerald-500 min-w-[60px]"
              style={{ width: `${Math.max(60, value.length * 8)}px` }}
            />
            <span className="text-emerald-400">"</span>
          </>
        ) : (
          <span className="text-emerald-400">"{value}"</span>
        )}
      </div>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <div className={indentClass}>
          <span className="text-sky-400">"{keyName}"</span>
          <span className="text-zinc-100">: []</span>
        </div>
      );
    }
    return (
      <div className={indentClass}>
        <span className="text-sky-400">"{keyName}"</span>
        <span className="text-zinc-100">: [</span>
        {value.map((item, idx) => (
          <JsonValue
            key={idx}
            keyName={String(idx)}
            value={item}
            path={[...path, String(idx)]}
            editable={editable}
            onValueChange={onValueChange}
            indent={indent + 1}
          />
        ))}
        <div className={indentClass}>
          <span className="text-zinc-100">]</span>
        </div>
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return (
        <div className={indentClass}>
          <span className="text-sky-400">"{keyName}"</span>
          <span className="text-zinc-100">{": {}"}</span>
        </div>
      );
    }
    return (
      <div className={indentClass}>
        <span className="text-sky-400">"{keyName}"</span>
        <span className="text-zinc-100">{": {"}</span>
        {entries.map(([k, v], idx) => (
          <React.Fragment key={k}>
            <JsonValue
              keyName={k}
              value={v}
              path={[...path, k]}
              editable={editable}
              onValueChange={onValueChange}
              indent={indent + 1}
            />
            {idx < entries.length - 1 && (
              <span className="text-zinc-500">,</span>
            )}
          </React.Fragment>
        ))}
        <div className={indentClass}>
          <span className="text-zinc-100">{"}"}</span>
        </div>
      </div>
    );
  }

  return null;
}

// CodeView sub-component
interface CodeViewProps {
  editable?: boolean;
  className?: string;
}

function CodeView({ editable = false, className }: CodeViewProps) {
  const { method, endpoint, body, onBodyChange } = useApiFormContext();

  const handleValueChange = (path: string[], value: unknown) => {
    if (!onBodyChange) return;

    const newBody = { ...body };
    let current: Record<string, unknown> = newBody;

    for (let i = 0; i < path.length - 1; i++) {
      const key = path[i];
      if (typeof current[key] === "object" && current[key] !== null) {
        current[key] = Array.isArray(current[key])
          ? [...(current[key] as unknown[])]
          : { ...(current[key] as Record<string, unknown>) };
        current = current[key] as Record<string, unknown>;
      }
    }

    const lastKey = path[path.length - 1];
    current[lastKey] = value;

    onBodyChange(newBody);
  };

  const entries = Object.entries(body);
  const hasBody = entries.length > 0;

  return (
    <TabsContent value="code" className={cn("py-4", className)}>
      <div className="rounded-lg bg-zinc-950 p-4 font-mono text-sm">
        {/* Method and endpoint */}
        <div className="flex items-center gap-2 mb-3">
          <span className={cn("font-semibold", methodColors[method])}>
            {method}
          </span>
          <span className="text-zinc-400">{endpoint}</span>
        </div>

        {/* Request body */}
        {hasBody && (
          <>
            <div className="text-zinc-400 text-xs mb-2">Request Body</div>
            <div className="text-zinc-100 text-xs leading-relaxed">
              <div>{"{"}</div>
              {entries.map(([key, value], idx) => (
                <React.Fragment key={key}>
                  <JsonValue
                    keyName={key}
                    value={value}
                    path={[key]}
                    editable={editable && !!onBodyChange}
                    onValueChange={handleValueChange}
                    indent={1}
                  />
                  {idx < entries.length - 1 && (
                    <span className="text-zinc-500 pl-4">,</span>
                  )}
                </React.Fragment>
              ))}
              <div>{"}"}</div>
            </div>
          </>
        )}
      </div>

      {editable && onBodyChange && (
        <p className="text-xs text-muted-foreground mt-3">
          Edit values above or use the Form tab for a guided experience.
        </p>
      )}
    </TabsContent>
  );
}

// Footer sub-component
interface FooterProps {
  children: React.ReactNode;
  className?: string;
}

function Footer({ children, className }: FooterProps) {
  return (
    <div
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className,
      )}
    >
      {children}
    </div>
  );
}

// Attach sub-components
ApiForm.Toggle = Toggle;
ApiForm.FormView = FormView;
ApiForm.CodeView = CodeView;
ApiForm.Footer = Footer;

export { ApiForm };
export type { ApiFormProps, HttpMethod };
