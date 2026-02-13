import React, { useState, useCallback, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Plus, X, Copy, Check } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { materialOceanic, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { DESIGN_SYSTEM } from "@/lib/design-system";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const uid = () => Math.random().toString(36).slice(2, 9);

// ─── Field & Operator definitions (mirror backend enums) ──────────────────────

interface FieldOption {
    value: string;
    label: string;
    category: "Base" | "Breadcrumbs" | "Metadata";
}

const FIELD_OPTIONS: FieldOption[] = [
    { value: "name", label: "Name", category: "Base" },
    { value: "entity_id", label: "Entity ID", category: "Base" },
    { value: "created_at", label: "Created at", category: "Base" },
    { value: "updated_at", label: "Updated at", category: "Base" },
    { value: "breadcrumbs.name", label: "Breadcrumb name", category: "Breadcrumbs" },
    { value: "breadcrumbs.entity_id", label: "Breadcrumb ID", category: "Breadcrumbs" },
    { value: "breadcrumbs.entity_type", label: "Breadcrumb type", category: "Breadcrumbs" },
    { value: "airweave_system_metadata.source_name", label: "Source", category: "Metadata" },
    { value: "airweave_system_metadata.entity_type", label: "Entity type", category: "Metadata" },
    { value: "airweave_system_metadata.original_entity_id", label: "Original ID", category: "Metadata" },
    { value: "airweave_system_metadata.chunk_index", label: "Chunk index", category: "Metadata" },
    { value: "airweave_system_metadata.sync_id", label: "Sync ID", category: "Metadata" },
    { value: "airweave_system_metadata.sync_job_id", label: "Sync job ID", category: "Metadata" },
];

const FIELD_CATEGORIES: { label: string; fields: FieldOption[] }[] = [
    { label: "Base", fields: FIELD_OPTIONS.filter((f) => f.category === "Base") },
    { label: "Breadcrumbs", fields: FIELD_OPTIONS.filter((f) => f.category === "Breadcrumbs") },
    { label: "Metadata", fields: FIELD_OPTIONS.filter((f) => f.category === "Metadata") },
];

interface OperatorOption {
    value: string;
    label: string;
}

const OPERATOR_OPTIONS: OperatorOption[] = [
    { value: "equals", label: "=" },
    { value: "not_equals", label: "≠" },
    { value: "contains", label: "∋" },
    { value: "greater_than", label: ">" },
    { value: "less_than", label: "<" },
    { value: "greater_than_or_equal", label: "≥" },
    { value: "less_than_or_equal", label: "≤" },
    { value: "in", label: "in" },
    { value: "not_in", label: "∉" },
];

// ─── Field-type classification (mirrors backend _TEXT_FIELDS / _DATE_FIELDS / _NUMERIC_FIELDS) ──

type FieldType = "text" | "date" | "numeric";

const FIELD_TYPE_MAP: Record<string, FieldType> = {
    name: "text",
    entity_id: "text",
    created_at: "date",
    updated_at: "date",
    "breadcrumbs.name": "text",
    "breadcrumbs.entity_id": "text",
    "breadcrumbs.entity_type": "text",
    "airweave_system_metadata.source_name": "text",
    "airweave_system_metadata.entity_type": "text",
    "airweave_system_metadata.original_entity_id": "text",
    "airweave_system_metadata.chunk_index": "numeric",
    "airweave_system_metadata.sync_id": "text",
    "airweave_system_metadata.sync_job_id": "text",
};

/** Which operators are valid for each field type. */
const OPERATORS_FOR_TYPE: Record<FieldType, Set<string>> = {
    text: new Set(["equals", "not_equals", "contains", "in", "not_in"]),
    date: new Set(["equals", "not_equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"]),
    numeric: new Set(["equals", "not_equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal", "in", "not_in"]),
};

/** Return the allowed operator options for a given field value (all if unknown). */
function operatorsForField(field: string): OperatorOption[] {
    const ft = FIELD_TYPE_MAP[field];
    if (!ft) return OPERATOR_OPTIONS; // no field selected yet → show all
    const allowed = OPERATORS_FOR_TYPE[ft];
    return OPERATOR_OPTIONS.filter((o) => allowed.has(o.value));
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface FilterCondition {
    id: string;
    field: string;
    operator: string;
    value: string;
}

export interface FilterGroup {
    id: string;
    conditions: FilterCondition[];
}

// ─── Factories ────────────────────────────────────────────────────────────────

const createCondition = (): FilterCondition => ({
    id: uid(),
    field: "",
    operator: "equals",
    value: "",
});

const createGroup = (): FilterGroup => ({
    id: uid(),
    conditions: [createCondition()],
});

// ─── Serialization ────────────────────────────────────────────────────────────

/** Parse value for list operators (in / not_in) into arrays. */
function serializeValue(value: string, operator: string): string | string[] {
    if ((operator === "in" || operator === "not_in") && value.includes(",")) {
        return value
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean);
    }
    return value;
}

/** Convert local FilterGroup[] → backend-ready payload (strips ids, handles list values). */
export function toBackendFilterGroups(groups: FilterGroup[]) {
    return groups
        .filter((g) => g.conditions.some((c) => c.field && c.value))
        .map((g) => ({
            conditions: g.conditions
                .filter((c) => c.field && c.value)
                .map((c) => ({
                    field: c.field,
                    operator: c.operator,
                    value: serializeValue(c.value, c.operator),
                })),
        }))
        .filter((g) => g.conditions.length > 0);
}

/** Count groups that have at least one complete condition. */
export function countActiveFilters(groups: FilterGroup[]): number {
    return groups.filter((g) => g.conditions.some((c) => c.field && c.value)).length;
}

// ─── Inline JSON preview ──────────────────────────────────────────────────────

function JsonPreview({ code, isDark }: { code: string; isDark: boolean }) {
    const [copied, setCopied] = useState(false);

    const baseStyle = isDark ? materialOceanic : oneLight;
    const customStyle = {
        ...baseStyle,
        'pre[class*="language-"]': {
            ...baseStyle['pre[class*="language-"]'],
            background: "transparent",
            margin: 0,
            padding: 0,
        },
        'code[class*="language-"]': {
            ...baseStyle['code[class*="language-"]'],
            background: "transparent",
        },
    };

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
    }, [code]);

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div
                className={cn(
                    "flex items-center justify-between px-2.5 py-1 border-b shrink-0",
                    isDark ? "border-border/20" : "border-border/30",
                )}
            >
                <span className="text-[9px] uppercase tracking-wider font-medium text-muted-foreground/50 select-none">
                    json
                </span>
                <button
                    type="button"
                    onClick={handleCopy}
                    className={cn(
                        "h-5 w-5 flex items-center justify-center rounded",
                        DESIGN_SYSTEM.transitions.fast,
                        "text-muted-foreground/30 hover:text-muted-foreground",
                    )}
                >
                    {copied ? <Check className="h-2.5 w-2.5" /> : <Copy className="h-2.5 w-2.5" />}
                </button>
            </div>
            {/* Body */}
            <div className="flex-1 overflow-auto px-2.5 py-2">
                <SyntaxHighlighter
                    language="json"
                    style={customStyle}
                    customStyle={{
                        fontSize: "0.65rem",
                        lineHeight: 1.5,
                        background: "transparent",
                        margin: 0,
                        padding: 0,
                    }}
                    wrapLongLines={false}
                    showLineNumbers={false}
                    codeTagProps={{
                        style: { fontSize: "0.65rem", fontFamily: "monospace" },
                    }}
                >
                    {code}
                </SyntaxHighlighter>
            </div>
        </div>
    );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface FilterBuilderPopoverProps {
    value: FilterGroup[];
    onChange: (groups: FilterGroup[]) => void;
    onClose: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export const FilterBuilderPopover: React.FC<FilterBuilderPopoverProps> = ({
    value,
    onChange,
    onClose,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // ─── Local editing state ─────────────────────────────────────────

    const [groups, setGroups] = useState<FilterGroup[]>(() =>
        value.length > 0
            ? value.map((g) => ({
                  ...g,
                  id: g.id || uid(),
                  conditions: g.conditions.map((c) => ({ ...c, id: c.id || uid() })),
              }))
            : [createGroup()],
    );

    // Re-sync when value prop changes while mounted
    useEffect(() => {
        if (value.length > 0) {
            setGroups(
                value.map((g) => ({
                    ...g,
                    id: g.id || uid(),
                    conditions: g.conditions.map((c) => ({ ...c, id: c.id || uid() })),
                })),
            );
        }
    }, []);

    // ─── Group handlers ──────────────────────────────────────────────

    const addGroup = useCallback(() => {
        setGroups((prev) => [...prev, createGroup()]);
    }, []);

    const removeGroup = useCallback((groupId: string) => {
        setGroups((prev) => {
            const next = prev.filter((g) => g.id !== groupId);
            return next.length === 0 ? [createGroup()] : next;
        });
    }, []);

    // ─── Condition handlers ──────────────────────────────────────────

    const addCondition = useCallback((groupId: string) => {
        setGroups((prev) =>
            prev.map((g) =>
                g.id === groupId
                    ? { ...g, conditions: [...g.conditions, createCondition()] }
                    : g,
            ),
        );
    }, []);

    const removeCondition = useCallback((groupId: string, conditionId: string) => {
        setGroups((prev) =>
            prev.map((g) => {
                if (g.id !== groupId) return g;
                const next = g.conditions.filter((c) => c.id !== conditionId);
                return { ...g, conditions: next.length === 0 ? [createCondition()] : next };
            }),
        );
    }, []);

    const updateCondition = useCallback(
        (groupId: string, conditionId: string, key: keyof FilterCondition, val: string) => {
            setGroups((prev) =>
                prev.map((g) => {
                    if (g.id !== groupId) return g;
                    return {
                        ...g,
                        conditions: g.conditions.map((c) => {
                            if (c.id !== conditionId) return c;
                            const updated = { ...c, [key]: val };

                            // When the field changes, ensure the current operator is
                            // still valid for the new field type.
                            if (key === "field") {
                                const allowed = operatorsForField(val);
                                if (!allowed.some((o) => o.value === updated.operator)) {
                                    updated.operator = allowed[0]?.value ?? "equals";
                                }
                            }
                            return updated;
                        }),
                    };
                }),
            );
        },
        [],
    );

    // ─── Actions ─────────────────────────────────────────────────────

    const handleApply = useCallback(() => {
        onChange(groups);
        onClose();
    }, [groups, onChange, onClose]);

    const handleClear = useCallback(() => {
        setGroups([createGroup()]);
    }, []);

    // ─── Live JSON preview ───────────────────────────────────────────

    const jsonOutput = useMemo(() => {
        const preview = groups.map((g) => ({
            conditions: g.conditions.map((c) => ({
                field: c.field || "<field>",
                operator: c.operator || "equals",
                value:
                    c.value ||
                    (c.operator === "in" || c.operator === "not_in"
                        ? "<val1, val2, ...>"
                        : "<value>"),
            })),
        }));
        return JSON.stringify(preview, null, 2);
    }, [groups]);

    // ─── Render ──────────────────────────────────────────────────────

    return (
        <div className="flex flex-col w-full h-full">
            {/* Header */}
            <div className={cn(
                "flex items-center justify-between px-3 py-2 border-b shrink-0",
                isDark ? "border-border/25" : "border-border/40",
            )}>
                <div>
                    <div className="text-[11px] font-semibold">Filters</div>
                    <div className="text-[9px] text-muted-foreground/60">
                        Conditions <span className="font-semibold text-foreground/50">AND</span> &middot;
                        Groups <span className="font-semibold text-foreground/50">OR</span>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={handleClear}
                    className={cn(
                        "text-[9px] text-muted-foreground/35 hover:text-muted-foreground px-1.5 py-0.5 rounded",
                        DESIGN_SYSTEM.transitions.fast,
                    )}
                >
                    Clear
                </button>
            </div>

            {/* ── Split body: builder + JSON ─────────────────────── */}
            <div className="flex-1 min-h-0 flex overflow-hidden">
                {/* ── Left: filter builder ───────────────────────── */}
                <div className="flex-1 min-w-0 overflow-y-auto p-2.5 space-y-1.5">
                    {groups.map((group, gi) => (
                        <React.Fragment key={group.id}>
                            {/* OR divider */}
                            {gi > 0 && (
                                <div className="flex items-center gap-2.5 py-0.5">
                                    <div
                                        className={cn(
                                            "flex-1 border-t border-dashed",
                                            isDark
                                                ? "border-muted-foreground/12"
                                                : "border-muted-foreground/15",
                                        )}
                                    />
                                    <span className="text-[8px] font-semibold text-muted-foreground/30 uppercase tracking-wider select-none">
                                        or
                                    </span>
                                    <div
                                        className={cn(
                                            "flex-1 border-t border-dashed",
                                            isDark
                                                ? "border-muted-foreground/12"
                                                : "border-muted-foreground/15",
                                        )}
                                    />
                                </div>
                            )}

                            {/* ── Group card ─────────────────────── */}
                            <div
                                className={cn(
                                    "rounded-md border p-2 space-y-1",
                                    isDark
                                        ? "border-border/20 bg-muted/5"
                                        : "border-border/30 bg-muted/15",
                                )}
                            >
                                {/* Condition rows */}
                                {group.conditions.map((cond, ci) => (
                                    <React.Fragment key={cond.id}>
                                        {/* AND label */}
                                        {ci > 0 && (
                                            <div className="flex justify-center -my-0.5">
                                                <span className="text-[8px] font-semibold text-muted-foreground/25 uppercase tracking-wider select-none">
                                                    and
                                                </span>
                                            </div>
                                        )}

                                        <div className="flex items-center gap-1">
                                            {/* Field */}
                                            <Select
                                                value={cond.field || undefined}
                                                onValueChange={(v) =>
                                                    updateCondition(group.id, cond.id, "field", v)
                                                }
                                            >
                                                <SelectTrigger
                                                    className={cn(
                                                        "h-6 w-[120px] text-[10px] shrink-0",
                                                        !cond.field && "text-muted-foreground",
                                                    )}
                                                >
                                                    <SelectValue placeholder="Field..." />
                                                </SelectTrigger>
                                                <SelectContent className="max-h-[220px]">
                                                    {FIELD_CATEGORIES.map((cat) => (
                                                        <React.Fragment key={cat.label}>
                                                            <div className="px-2 pt-1.5 pb-0.5 text-[8px] font-medium tracking-wider uppercase text-muted-foreground/40 select-none">
                                                                {cat.label}
                                                            </div>
                                                            {cat.fields.map((f) => (
                                                                <SelectItem
                                                                    key={f.value}
                                                                    value={f.value}
                                                                    className="text-[10px]"
                                                                >
                                                                    {f.label}
                                                                </SelectItem>
                                                            ))}
                                                        </React.Fragment>
                                                    ))}
                                                </SelectContent>
                                            </Select>

                                            {/* Operator */}
                                            <Select
                                                value={cond.operator}
                                                onValueChange={(v) =>
                                                    updateCondition(group.id, cond.id, "operator", v)
                                                }
                                            >
                                                <SelectTrigger className="h-6 w-[52px] text-[10px] shrink-0">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {operatorsForField(cond.field).map((o) => (
                                                        <SelectItem
                                                            key={o.value}
                                                            value={o.value}
                                                            className="text-[10px]"
                                                        >
                                                            {o.label}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>

                                            {/* Value */}
                                            <input
                                                type="text"
                                                value={cond.value}
                                                onChange={(e) =>
                                                    updateCondition(group.id, cond.id, "value", e.target.value)
                                                }
                                                placeholder={
                                                    cond.operator === "in" || cond.operator === "not_in"
                                                        ? "a, b, c"
                                                        : "Value..."
                                                }
                                                className={cn(
                                                    "h-6 flex-1 min-w-0 px-1.5 rounded-md border text-[10px]",
                                                    "bg-background outline-none",
                                                    "focus:ring-1 focus:ring-ring focus:border-ring",
                                                    "border-input",
                                                    "placeholder:text-muted-foreground/30",
                                                )}
                                            />

                                            {/* Remove */}
                                            <button
                                                type="button"
                                                onClick={() => removeCondition(group.id, cond.id)}
                                                className={cn(
                                                    "h-6 w-6 shrink-0 rounded flex items-center justify-center",
                                                    DESIGN_SYSTEM.transitions.fast,
                                                    "text-muted-foreground/15 hover:text-destructive hover:bg-destructive/10",
                                                )}
                                            >
                                                <X className="h-2.5 w-2.5" />
                                            </button>
                                        </div>
                                    </React.Fragment>
                                ))}

                                {/* + AND / remove group row */}
                                <div className="flex items-center justify-between pt-0.5">
                                    <button
                                        type="button"
                                        onClick={() => addCondition(group.id)}
                                        className={cn(
                                            "flex items-center gap-0.5 text-[9px] font-medium px-1 py-0.5 rounded",
                                            DESIGN_SYSTEM.transitions.fast,
                                            "text-muted-foreground/40 hover:text-foreground hover:bg-muted/50",
                                        )}
                                    >
                                        <Plus className="h-2 w-2" />
                                        AND
                                    </button>
                                    {groups.length > 1 && (
                                        <button
                                            type="button"
                                            onClick={() => removeGroup(group.id)}
                                            className={cn(
                                                "text-[9px] px-1 py-0.5 rounded",
                                                DESIGN_SYSTEM.transitions.fast,
                                                "text-muted-foreground/20 hover:text-destructive hover:bg-destructive/10",
                                            )}
                                        >
                                            Remove
                                        </button>
                                    )}
                                </div>
                            </div>
                        </React.Fragment>
                    ))}

                    {/* + OR group */}
                    <button
                        type="button"
                        onClick={addGroup}
                        className={cn(
                            "flex items-center gap-1 text-[9px] font-medium px-2.5 py-1.5 rounded-md",
                            "border border-dashed w-full justify-center",
                            DESIGN_SYSTEM.transitions.standard,
                            isDark
                                ? "border-border/20 text-muted-foreground/30 hover:text-muted-foreground/60 hover:border-border/40 hover:bg-muted/10"
                                : "border-border/30 text-muted-foreground/40 hover:text-muted-foreground/70 hover:border-border/50 hover:bg-muted/10",
                        )}
                    >
                        <Plus className="h-2.5 w-2.5" />
                        OR group
                    </button>
                </div>

                {/* ── Right: live JSON output ────────────────────── */}
                <div
                    className={cn(
                        "w-[220px] shrink-0 border-l",
                        isDark ? "border-border/20 bg-black/20" : "border-border/25 bg-muted/30",
                    )}
                >
                    <JsonPreview code={jsonOutput} isDark={isDark} />
                </div>
            </div>

            {/* ── Footer ──────────────────────────────────────────── */}
            <div className={cn(
                "flex items-center justify-end gap-1.5 px-3 py-2 border-t shrink-0",
                isDark ? "border-border/25" : "border-border/40",
            )}>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onClose}
                    className="h-6 text-[10px] px-2.5"
                >
                    Cancel
                </Button>
                <Button
                    size="sm"
                    onClick={handleApply}
                    className="h-6 text-[10px] px-2.5"
                >
                    Apply
                </Button>
            </div>
        </div>
    );
};
