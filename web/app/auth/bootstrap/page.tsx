"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

export default function BootstrapPage() {
  const router = useRouter();
  const { bootstrapFirstUser } = useAuth();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setSubmitting(true);
    const toastId = toast.loading("Creating first user...");
    try {
      await bootstrapFirstUser({ email: email.trim(), displayName: displayName.trim() });
      toast.success("Bootstrap successful. You are now signed in.", { id: toastId });
      router.replace("/projects");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Bootstrap failed.", { id: toastId });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Bootstrap first account</CardTitle>
          <CardDescription>
            This endpoint only works while the system has no users.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="owner@example.com"
                required
                disabled={submitting}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="display-name">Display name</Label>
              <Input
                id="display-name"
                type="text"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Owner"
                required
                disabled={submitting}
              />
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting ? <Spinner size="sm" className="mr-2" /> : null}
              {submitting ? "Bootstrapping..." : "Bootstrap and sign in"}
            </Button>
          </form>

          <p className="mt-4 text-sm text-muted-foreground">
            Already have a token?{" "}
            <Link className="text-primary underline" href="/auth/login">
              Go to sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
