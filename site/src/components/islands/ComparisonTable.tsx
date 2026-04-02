import { Fragment, useState, useMemo, useCallback } from "react";
import "./ComparisonTable.css";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface Dimension {
  key: string;
  label: string;
  description: string;
}

interface Category {
  key: string;
  label: string;
}

interface FeatureEntry {
  support: "full" | "partial" | "none" | "planned";
  note: string;
}

interface Competitor {
  name: string;
  slug: string;
  url?: string;
  repo?: string;
  description: string;
  license: string;
  language: string;
  category: string;
  is_synthorg?: boolean;
  features: Record<string, FeatureEntry>;
}

interface Props {
  competitors: Competitor[];
  dimensions: Dimension[];
  categories: Category[];
}

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const SUPPORT_ORDER: Record<string, number> = {
  full: 0,
  partial: 1,
  planned: 2,
  none: 3,
};

const SUPPORT_ICONS: Record<string, string> = {
  full: "\u2714",
  partial: "~",
  none: "-",
  planned: "\u23f2",
};

const SUPPORT_LABELS: Record<string, string> = {
  full: "Full support",
  partial: "Partial support",
  none: "Not supported",
  planned: "Planned",
};

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function SupportIcon({ level, note }: { level: string; note?: string }) {
  return (
    <span
      className="ct-support"
      data-level={level}
      title={note || SUPPORT_LABELS[level] || level}
    >
      {SUPPORT_ICONS[level] || level}
    </span>
  );
}

function SortArrow({
  column,
  sortBy,
}: {
  column: string;
  sortBy: { key: string; direction: "asc" | "desc" };
}) {
  const active = sortBy.key === column;
  const arrow = active && sortBy.direction === "desc" ? "\u25BC" : "\u25B2";
  return (
    <span className="sort-arrow" data-active={active ? "true" : "false"}>
      {arrow}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export default function ComparisonTable({
  competitors,
  dimensions,
  categories,
}: Props) {
  // -- State --
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<{
    key: string;
    direction: "asc" | "desc";
  }>({ key: "name", direction: "asc" });
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // -- Category lookup --
  const categoryMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const cat of categories) {
      map[cat.key] = cat.label;
    }
    return map;
  }, [categories]);

  // -- Filtering --
  const filtered = useMemo(() => {
    let result = competitors;

    if (categoryFilter) {
      result = result.filter((c) => c.category === categoryFilter);
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.description.toLowerCase().includes(q) ||
          c.license.toLowerCase().includes(q),
      );
    }

    return result;
  }, [competitors, categoryFilter, search]);

  // -- Sorting (SynthOrg always pinned to top) --
  const sorted = useMemo(() => {
    const synthorg = filtered.filter((c) => c.is_synthorg);
    const rest = filtered.filter((c) => !c.is_synthorg);

    rest.sort((a, b) => {
      const dir = sortBy.direction === "asc" ? 1 : -1;

      if (sortBy.key === "name") {
        return dir * a.name.localeCompare(b.name);
      }
      if (sortBy.key === "license") {
        return dir * a.license.localeCompare(b.license);
      }
      if (sortBy.key === "category") {
        const catA = categoryMap[a.category] || a.category;
        const catB = categoryMap[b.category] || b.category;
        return dir * catA.localeCompare(catB);
      }

      // Sort by dimension support level
      const featA = a.features[sortBy.key];
      const featB = b.features[sortBy.key];
      const orderA = SUPPORT_ORDER[featA?.support || "none"] ?? 3;
      const orderB = SUPPORT_ORDER[featB?.support || "none"] ?? 3;
      if (orderA !== orderB) return dir * (orderA - orderB);
      return a.name.localeCompare(b.name);
    });

    return [...synthorg, ...rest];
  }, [filtered, sortBy, categoryMap]);

  // -- Handlers --
  const handleSort = useCallback(
    (key: string) => {
      setSortBy((prev) =>
        prev.key === key
          ? { key, direction: prev.direction === "asc" ? "desc" : "asc" }
          : { key, direction: "asc" },
      );
    },
    [],
  );

  const toggleExpanded = useCallback((slug: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
      } else {
        next.add(slug);
      }
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setCategoryFilter(null);
    setSearch("");
  }, []);

  const hasFilters = categoryFilter !== null || search.trim() !== "";

  // -- Unique categories present in data --
  const availableCategories = useMemo(() => {
    const seen = new Set<string>();
    for (const c of competitors) {
      if (c.category) seen.add(c.category);
    }
    return categories.filter((cat) => seen.has(cat.key));
  }, [competitors, categories]);

  return (
    <div className="comparison-table">
      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: "1rem",
          marginBottom: "1rem",
          fontSize: "0.8125rem",
          color: "var(--ct-text-muted)",
          flexWrap: "wrap",
        }}
      >
        <span>
          <SupportIcon level="full" /> Full
        </span>
        <span>
          <SupportIcon level="partial" /> Partial
        </span>
        <span>
          <SupportIcon level="planned" /> Planned
        </span>
        <span>
          <SupportIcon level="none" /> None
        </span>
      </div>

      {/* Filter bar */}
      <div className="ct-filter-bar">
        <input
          type="text"
          className="ct-search"
          placeholder="Search frameworks..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search frameworks"
        />
        {availableCategories.map((cat) => (
          <button
            key={cat.key}
            className="ct-filter-btn"
            data-active={categoryFilter === cat.key ? "true" : "false"}
            onClick={() =>
              setCategoryFilter((prev) =>
                prev === cat.key ? null : cat.key,
              )
            }
          >
            {cat.label}
          </button>
        ))}
        {hasFilters && (
          <button className="ct-clear-btn" onClick={clearFilters}>
            Clear
          </button>
        )}
      </div>

      {/* Result count */}
      <div className="ct-result-count">
        Showing {sorted.length} of {competitors.length} frameworks
      </div>

      {/* Desktop: Table view */}
      <div className="ct-table-wrap">
        <table className="ct-table">
          <thead>
            <tr>
              <th style={{ width: "2rem" }}></th>
              <th onClick={() => handleSort("name")}>
                Framework
                <SortArrow column="name" sortBy={sortBy} />
              </th>
              <th onClick={() => handleSort("category")}>
                Category
                <SortArrow column="category" sortBy={sortBy} />
              </th>
              <th onClick={() => handleSort("license")}>
                License
                <SortArrow column="license" sortBy={sortBy} />
              </th>
              {dimensions.map((dim) => (
                <th
                  key={dim.key}
                  onClick={() => handleSort(dim.key)}
                  title={dim.description}
                >
                  {dim.label}
                  <SortArrow column={dim.key} sortBy={sortBy} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((comp) => {
              const isExpanded = expandedRows.has(comp.slug);
              return (
                <Fragment key={comp.slug}>
                  <tr
                    data-synthorg={comp.is_synthorg ? "true" : "false"}
                  >
                    <td>
                      <button
                        className="ct-expand-btn"
                        data-open={isExpanded ? "true" : "false"}
                        onClick={() => toggleExpanded(comp.slug)}
                        aria-label={`${isExpanded ? "Collapse" : "Expand"} ${comp.name} details`}
                      >
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <path d="m6 9 6 6 6-6" />
                        </svg>
                      </button>
                    </td>
                    <td>
                      <div className="ct-name-cell">
                        {comp.url ? (
                          <a
                            href={comp.url}
                            className={
                              comp.is_synthorg
                                ? "ct-name-link ct-name-synthorg"
                                : "ct-name-link"
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {comp.name}
                          </a>
                        ) : (
                          <span
                            className={
                              comp.is_synthorg
                                ? "ct-name-synthorg"
                                : undefined
                            }
                          >
                            {comp.name}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="ct-category-badge">
                        {categoryMap[comp.category] || comp.category}
                      </span>
                    </td>
                    <td>
                      <span className="ct-license">{comp.license}</span>
                    </td>
                    {dimensions.map((dim) => {
                      const feat = comp.features[dim.key];
                      const support = feat?.support || "none";
                      const note = feat?.note || "";
                      return (
                        <td key={dim.key} style={{ textAlign: "center" }}>
                          <SupportIcon level={support} note={note} />
                        </td>
                      );
                    })}
                  </tr>
                  {isExpanded && (
                    <tr
                      className="ct-detail-row"
                    >
                      <td colSpan={4 + dimensions.length}>
                        <div className="ct-detail-content">
                          <div className="ct-detail-item" style={{ gridColumn: "1 / -1" }}>
                            <span className="ct-detail-label">Description</span>
                            <span className="ct-detail-value">
                              {comp.description}
                              {comp.repo && (
                                <>
                                  {" "}
                                  <a
                                    href={comp.repo}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ color: "var(--ct-accent)" }}
                                  >
                                    Repository
                                  </a>
                                </>
                              )}
                            </span>
                          </div>
                          {dimensions.map((dim) => {
                            const feat = comp.features[dim.key];
                            if (!feat?.note) return null;
                            return (
                              <div key={dim.key} className="ct-detail-item">
                                <span className="ct-detail-label">
                                  {dim.label}
                                </span>
                                <span className="ct-detail-value">
                                  {feat.note}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile: Card view */}
      <div className="ct-cards">
        {sorted.map((comp) => (
          <div
            key={comp.slug}
            className="ct-card"
            data-synthorg={comp.is_synthorg ? "true" : "false"}
          >
            <div className="ct-card-header">
              <div>
                {comp.url ? (
                  <a
                    href={comp.url}
                    className={`ct-card-name ${comp.is_synthorg ? "ct-name-synthorg" : ""}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: "none" }}
                  >
                    {comp.name}
                  </a>
                ) : (
                  <span className={`ct-card-name ${comp.is_synthorg ? "ct-name-synthorg" : ""}`}>
                    {comp.name}
                  </span>
                )}
              </div>
              <div className="ct-card-meta">
                <span className="ct-category-badge">
                  {categoryMap[comp.category] || comp.category}
                </span>
                <span className="ct-license">{comp.license}</span>
              </div>
            </div>
            <p
              style={{
                fontSize: "0.8125rem",
                color: "var(--ct-text-secondary)",
                marginBottom: "0.75rem",
              }}
            >
              {comp.description}
            </p>
            <div className="ct-card-grid">
              {dimensions.map((dim) => {
                const feat = comp.features[dim.key];
                const support = feat?.support || "none";
                return (
                  <div key={dim.key} className="ct-card-feature">
                    <SupportIcon level={support} />
                    <span>{dim.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {sorted.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "3rem",
            color: "var(--ct-text-muted)",
          }}
        >
          No frameworks match your filters.{" "}
          <button
            onClick={clearFilters}
            style={{
              color: "var(--ct-accent)",
              background: "none",
              border: "none",
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}
