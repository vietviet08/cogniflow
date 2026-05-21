"use client";

import { useCallback, useState, useRef } from "react";
import { toast } from "sonner";
import {
    Search,
    Globe,
    Plus,
    Check,
    ExternalLink,
    Clock,
    User,
    Tag,
    Loader2,
    X,
    BookOpen,
    AlignLeft,
} from "lucide-react";

import { searchWeb, previewWebUrl, ingestSourceUrl } from "@/lib/api/client";
import type { WebSearchResult, WebPreviewResult } from "@/lib/api/types";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";

interface WebSourceDiscoveryProps {
    projectId: string;
    canMutate: boolean;
    /** Set of source URLs already added to the project */
    addedUrls: Set<string>;
    onSourceAdded: () => void;
}

export function WebSourceDiscovery({
    projectId,
    canMutate,
    addedUrls,
    onSourceAdded,
}: WebSourceDiscoveryProps) {
    const [query, setQuery] = useState("");
    const [isSearching, setIsSearching] = useState(false);
    const [results, setResults] = useState<WebSearchResult[]>([]);
    const [hasSearched, setHasSearched] = useState(false);

    const [selectedResult, setSelectedResult] = useState<WebSearchResult | null>(null);
    const [preview, setPreview] = useState<WebPreviewResult | null>(null);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    const [addingUrl, setAddingUrl] = useState<string | null>(null);
    // Track URLs added during this session for instant feedback
    const [locallyAdded, setLocallyAdded] = useState<Set<string>>(new Set());

    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const searchInputRef = useRef<HTMLInputElement>(null);

    const isAdded = (url: string) => addedUrls.has(url) || locallyAdded.has(url);

    // ----------------------------------------------------------------
    // Search
    // ----------------------------------------------------------------

    const runSearch = useCallback(
        async (q: string) => {
            if (!q.trim()) {
                setResults([]);
                setHasSearched(false);
                return;
            }
            setIsSearching(true);
            setHasSearched(true);
            setSelectedResult(null);
            setPreview(null);
            try {
                const res = await searchWeb(q.trim(), 10);
                setResults(res.data.items);
            } catch (err) {
                toast.error(
                    err instanceof Error ? err.message : "Search failed.",
                );
                setResults([]);
            } finally {
                setIsSearching(false);
            }
        },
        [],
    );

    function handleQueryChange(value: string) {
        setQuery(value);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => runSearch(value), 600);
    }

    function handleSearchSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (debounceRef.current) clearTimeout(debounceRef.current);
        runSearch(query);
    }

    // ----------------------------------------------------------------
    // Preview
    // ----------------------------------------------------------------

    async function handleSelectResult(result: WebSearchResult) {
        setSelectedResult(result);
        setPreview(null);
        setIsLoadingPreview(true);
        try {
            const res = await previewWebUrl(result.url);
            setPreview(res.data);
        } catch (err) {
            toast.error(
                err instanceof Error
                    ? err.message
                    : "Failed to load preview.",
            );
        } finally {
            setIsLoadingPreview(false);
        }
    }

    // ----------------------------------------------------------------
    // Add to project
    // ----------------------------------------------------------------

    async function handleAddSource(url: string) {
        if (!canMutate) {
            toast.error("This action requires editor role or higher.");
            return;
        }
        setAddingUrl(url);
        const toastId = toast.loading("Adding web source to project...");
        try {
            await ingestSourceUrl({ projectId, url });
            setLocallyAdded((prev) => new Set([...prev, url]));
            onSourceAdded();
            toast.success("Web source added. Run processing to index it.", {
                id: toastId,
            });
        } catch (err) {
            toast.error(
                err instanceof Error ? err.message : "Failed to add source.",
                { id: toastId },
            );
        } finally {
            setAddingUrl(null);
        }
    }

    // ----------------------------------------------------------------
    // Render
    // ----------------------------------------------------------------

    return (
        <div className="flex flex-col gap-4 h-full">
            {/* Search Bar */}
            <form onSubmit={handleSearchSubmit} className="flex gap-2">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    <Input
                        ref={searchInputRef}
                        id="web-source-search-input"
                        placeholder="Search for web sources… e.g. 'machine learning transformers'"
                        value={query}
                        onChange={(e) => handleQueryChange(e.target.value)}
                        className="pl-9"
                        disabled={isSearching}
                    />
                </div>
                <Button
                    type="submit"
                    variant="secondary"
                    disabled={isSearching || !query.trim()}
                >
                    {isSearching ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Search className="h-4 w-4" />
                    )}
                </Button>
            </form>

            {/* Body: split pane when results exist */}
            <div className="flex gap-4 flex-col lg:flex-row min-h-0 flex-1">
                {/* Left: Results List */}
                <div className="flex flex-col gap-2 lg:w-96 lg:min-w-96 min-h-[200px]">
                    {isSearching && (
                        <div className="flex flex-col items-center justify-center gap-3 py-10 text-muted-foreground">
                            <Loader2 className="h-6 w-6 animate-spin text-primary" />
                            <p className="text-sm">Searching the web…</p>
                        </div>
                    )}

                    {!isSearching && !hasSearched && (
                        <div className="flex flex-col items-center justify-center gap-3 py-10 text-muted-foreground text-center">
                            <div className="rounded-full bg-primary/10 p-3">
                                <Globe className="h-6 w-6 text-primary" />
                            </div>
                            <div>
                                <p className="text-sm font-medium">Discover web sources</p>
                                <p className="text-xs mt-1 max-w-xs">
                                    Type a keyword above to search for relevant websites and articles you can add to this project.
                                </p>
                            </div>
                        </div>
                    )}

                    {!isSearching && hasSearched && results.length === 0 && (
                        <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground text-center">
                            <Search className="h-6 w-6" />
                            <p className="text-sm">No results found for "{query}"</p>
                            <p className="text-xs">Try different keywords</p>
                        </div>
                    )}

                    {!isSearching && results.length > 0 && (
                        <div className="flex flex-col gap-1.5 overflow-y-auto max-h-[520px] pr-1">
                            {results.map((result) => {
                                const added = isAdded(result.url);
                                const isSelected = selectedResult?.url === result.url;
                                return (
                                    <button
                                        key={result.url}
                                        type="button"
                                        onClick={() => handleSelectResult(result)}
                                        className={[
                                            "w-full text-left rounded-lg border p-3 transition-all hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                            isSelected
                                                ? "border-primary/60 bg-primary/5 shadow-sm"
                                                : "border-border hover:border-primary/30 hover:bg-muted/40",
                                        ].join(" ")}
                                    >
                                        <div className="flex items-start gap-2.5">
                                            {/* Favicon */}
                                            <div className="mt-0.5 shrink-0">
                                                {result.favicon_url ? (
                                                    <img
                                                        src={result.favicon_url}
                                                        alt=""
                                                        width={16}
                                                        height={16}
                                                        className="rounded-sm"
                                                        onError={(e) => {
                                                            (e.target as HTMLImageElement).style.display = "none";
                                                        }}
                                                    />
                                                ) : (
                                                    <Globe className="h-4 w-4 text-muted-foreground" />
                                                )}
                                            </div>

                                            <div className="flex-1 min-w-0">
                                                {/* Domain + Added badge */}
                                                <div className="flex items-center gap-1.5 mb-0.5">
                                                    <span className="text-xs text-muted-foreground truncate">
                                                        {result.domain}
                                                    </span>
                                                    {added && (
                                                        <Badge
                                                            variant="secondary"
                                                            className="text-[10px] px-1.5 py-0 h-4 gap-1 shrink-0 bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20"
                                                        >
                                                            <Check className="h-2.5 w-2.5" />
                                                            Added
                                                        </Badge>
                                                    )}
                                                </div>

                                                {/* Title */}
                                                <p className="text-sm font-medium leading-snug line-clamp-2">
                                                    {result.title}
                                                </p>

                                                {/* Snippet */}
                                                {result.snippet && (
                                                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                                                        {result.snippet}
                                                    </p>
                                                )}
                                            </div>

                                            {/* Quick add button */}
                                            <div
                                                className="shrink-0 mt-0.5"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    if (!added) handleAddSource(result.url);
                                                }}
                                            >
                                                {added ? (
                                                    <div className="h-7 w-7 rounded-full bg-green-500/10 flex items-center justify-center">
                                                        <Check className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                                                    </div>
                                                ) : addingUrl === result.url ? (
                                                    <div className="h-7 w-7 rounded-full flex items-center justify-center">
                                                        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                                                    </div>
                                                ) : (
                                                    <div
                                                        className="h-7 w-7 rounded-full border border-primary/30 hover:bg-primary/10 hover:border-primary flex items-center justify-center transition-colors cursor-pointer"
                                                        title="Add to project"
                                                    >
                                                        <Plus className="h-3.5 w-3.5 text-primary" />
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Right: Preview Panel */}
                {(selectedResult || isLoadingPreview) && (
                    <>
                        <Separator orientation="vertical" className="hidden lg:block h-auto" />
                        <div className="flex-1 min-w-0">
                            <PreviewPanel
                                result={selectedResult}
                                preview={preview}
                                isLoading={isLoadingPreview}
                                isAdded={selectedResult ? isAdded(selectedResult.url) : false}
                                isAdding={selectedResult ? addingUrl === selectedResult.url : false}
                                canMutate={canMutate}
                                onAdd={() => selectedResult && handleAddSource(selectedResult.url)}
                                onClose={() => {
                                    setSelectedResult(null);
                                    setPreview(null);
                                }}
                            />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

// ----------------------------------------------------------------
// Preview Panel sub-component
// ----------------------------------------------------------------

interface PreviewPanelProps {
    result: WebSearchResult | null;
    preview: WebPreviewResult | null;
    isLoading: boolean;
    isAdded: boolean;
    isAdding: boolean;
    canMutate: boolean;
    onAdd: () => void;
    onClose: () => void;
}

function PreviewPanel({
    result,
    preview,
    isLoading,
    isAdded,
    isAdding,
    canMutate,
    onAdd,
    onClose,
}: PreviewPanelProps) {
    const data = preview ?? (result ? { ...result, description: null } : null);

    return (
        <Card className="h-full flex flex-col overflow-hidden border-primary/20">
            <CardHeader className="pb-3 shrink-0">
                <div className="flex items-start gap-3">
                    {/* Favicon */}
                    <div className="mt-1 shrink-0">
                        {data?.favicon_url ? (
                            <img
                                src={data.favicon_url}
                                alt=""
                                width={20}
                                height={20}
                                className="rounded-sm"
                                onError={(e) =>
                                    ((e.target as HTMLImageElement).style.display = "none")
                                }
                            />
                        ) : (
                            <Globe className="h-5 w-5 text-muted-foreground" />
                        )}
                    </div>

                    <div className="flex-1 min-w-0">
                        <span className="text-xs text-muted-foreground">
                            {(preview?.domain ?? result?.domain) || ""}
                        </span>
                        <CardTitle className="text-base leading-snug mt-0.5 line-clamp-3">
                            {isLoading ? (
                                <span className="inline-block w-48 h-4 bg-muted animate-pulse rounded" />
                            ) : (
                                (preview?.title ?? result?.title ?? "Loading…")
                            )}
                        </CardTitle>
                    </div>

                    {/* Close */}
                    <Button
                        size="icon"
                        variant="ghost"
                        className="shrink-0 h-7 w-7"
                        onClick={onClose}
                    >
                        <X className="h-4 w-4" />
                    </Button>
                </div>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto space-y-4">
                {isLoading && (
                    <div className="space-y-3">
                        {[...Array(4)].map((_, i) => (
                            <div
                                key={i}
                                className="h-3 bg-muted animate-pulse rounded"
                                style={{ width: `${70 + (i % 3) * 10}%` }}
                            />
                        ))}
                    </div>
                )}

                {!isLoading && preview && (
                    <>
                        {/* Meta info */}
                        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                            {preview.author && (
                                <div className="flex items-center gap-1">
                                    <User className="h-3 w-3" />
                                    <span>{preview.author}</span>
                                </div>
                            )}
                            {preview.published_at && (
                                <div className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    <span>{new Date(preview.published_at).toLocaleDateString()}</span>
                                </div>
                            )}
                            {preview.estimated_word_count > 0 && (
                                <div className="flex items-center gap-1">
                                    <BookOpen className="h-3 w-3" />
                                    <span>
                                        ~{preview.estimated_reading_time_minutes} min read
                                        &nbsp;·&nbsp;
                                        {preview.estimated_word_count.toLocaleString()} words
                                    </span>
                                </div>
                            )}
                            {preview.language && preview.language !== "unknown" && (
                                <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                                    {preview.language.toUpperCase()}
                                </Badge>
                            )}
                        </div>

                        {/* Description */}
                        {preview.description && (
                            <div>
                                <p className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wide">
                                    Description
                                </p>
                                <p className="text-sm leading-relaxed text-foreground/80">
                                    {preview.description}
                                </p>
                            </div>
                        )}

                        {/* Content Preview */}
                        {preview.content_preview && (
                            <div>
                                <p className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wide flex items-center gap-1">
                                    <AlignLeft className="h-3 w-3" />
                                    Content Preview
                                </p>
                                <div className="relative">
                                    <p className="text-sm leading-relaxed text-foreground/70 line-clamp-6">
                                        {preview.content_preview}
                                    </p>
                                    {/* Fade out at bottom */}
                                    <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-card to-transparent pointer-events-none" />
                                </div>
                            </div>
                        )}

                        {/* Tags */}
                        {preview.tags.length > 0 && (
                            <div>
                                <p className="text-xs font-medium text-muted-foreground mb-1.5 uppercase tracking-wide flex items-center gap-1">
                                    <Tag className="h-3 w-3" />
                                    Tags
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                    {preview.tags.slice(0, 8).map((tag) => (
                                        <Badge
                                            key={tag}
                                            variant="secondary"
                                            className="text-[11px] h-5 px-2"
                                        >
                                            {tag}
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* Snippet fallback when preview hasn't loaded or result only */}
                {!isLoading && !preview && result?.snippet && (
                    <p className="text-sm text-foreground/70 leading-relaxed">
                        {result.snippet}
                    </p>
                )}
            </CardContent>

            {/* Footer CTA */}
            <div className="p-4 border-t shrink-0 flex gap-2">
                <Button
                    className="flex-1"
                    disabled={!canMutate || isAdded || isAdding || isLoading}
                    onClick={onAdd}
                    id="web-source-preview-add-btn"
                >
                    {isAdding ? (
                        <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Adding…
                        </>
                    ) : isAdded ? (
                        <>
                            <Check className="h-4 w-4 mr-2 text-green-500" />
                            Added to Project
                        </>
                    ) : (
                        <>
                            <Plus className="h-4 w-4 mr-2" />
                            Add to Project
                        </>
                    )}
                </Button>

                {result?.url && (
                    <a
                        href={result.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open original page"
                        className="inline-flex items-center justify-center rounded-md border border-input bg-background h-10 w-10 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors shrink-0"
                    >
                        <ExternalLink className="h-4 w-4" />
                    </a>
                )}
            </div>
        </Card>
    );
}
