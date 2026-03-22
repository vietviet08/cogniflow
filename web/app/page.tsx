import Link from "next/link";
import {
  FolderOpen,
  Database,
  Search,
  Lightbulb,
  FileText,
  ArrowRight,
  BrainCircuit,
  Sparkles,
} from "lucide-react";

import { PageWrapper } from "@/components/layout/page-wrapper";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const quickLinks = [
  {
    href: "/projects",
    label: "Projects",
    description: "Create and manage research projects",
    icon: FolderOpen,
    badge: "Start here",
    badgeVariant: "default" as const,
    color: "text-blue-500",
    bg: "bg-blue-500/10",
  },
  {
    href: "/sources",
    label: "Sources",
    description: "Upload PDFs or ingest URLs and arXiv papers",
    icon: Database,
    color: "text-violet-500",
    bg: "bg-violet-500/10",
  },
  {
    href: "/query",
    label: "Query",
    description: "Ask questions across your indexed knowledge base",
    icon: Search,
    color: "text-amber-500",
    bg: "bg-amber-500/10",
  },
  {
    href: "/insights",
    label: "Insights",
    description: "Discover patterns and key concepts",
    icon: Lightbulb,
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
  },
  {
    href: "/reports",
    label: "Reports",
    description: "Generate and export research summaries",
    icon: FileText,
    color: "text-rose-500",
    bg: "bg-rose-500/10",
  },
];

export default function HomePage() {
  return (
    <PageWrapper>
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border border-border p-8">
        <div className="relative z-10 flex flex-col gap-3 max-w-xl">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md">
              <BrainCircuit className="h-5 w-5" />
            </div>
            <Badge variant="secondary" className="gap-1">
              <Sparkles className="h-3 w-3" />
              AI-Powered
            </Badge>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Welcome to NoteMesh
          </h1>
          <p className="text-muted-foreground text-sm leading-relaxed">
            Your AI research infrastructure. Create a project, ingest documents,
            then query your knowledge base with natural language.
          </p>
        </div>
        {/* Decorative */}
        <div className="pointer-events-none absolute right-0 top-0 h-full w-1/2 bg-gradient-to-l from-primary/5 to-transparent" />
      </div>

      {/* Quick Links */}
      <div>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-muted-foreground">
          Get Started
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {quickLinks.map(({ href, label, description, icon: Icon, badge, badgeVariant, color, bg }) => (
            <Link key={href} href={href} className="group">
              <Card className="h-full transition-all duration-200 group-hover:shadow-md group-hover:border-primary/30 group-hover:-translate-y-0.5">
                <CardHeader className="pb-3">
                  <div className="mb-3 flex items-center justify-between">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${bg}`}>
                      <Icon className={`h-4 w-4 ${color}`} />
                    </div>
                    {badge && (
                      <Badge variant={badgeVariant} className="text-[10px]">
                        {badge}
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="text-base">{label}</CardTitle>
                  <CardDescription className="text-xs leading-relaxed">
                    {description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="flex items-center gap-1 text-xs font-medium text-primary opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:gap-2">
                    Open <ArrowRight className="h-3 w-3" />
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </PageWrapper>
  );
}
