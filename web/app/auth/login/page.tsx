"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

export default function LoginPage() {
    const { token, user, isLoading, loginWithPassword } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const nextPath = searchParams.get("next") || "/projects";

    useEffect(() => {
        if (!isLoading && token && user) {
            router.replace(nextPath);
        }
    }, [isLoading, token, user, router, nextPath]);

    async function handleSubmit(event: React.SyntheticEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!email.trim() || !password.trim()) {
            toast.error("Please enter both email and password.");
            return;
        }

        setSubmitting(true);
        const toastId = toast.loading("Signing in...");
        try {
            await loginWithPassword({ email: email.trim(), password });
            toast.success("Signed in successfully.", { id: toastId });
            router.replace(nextPath);
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Failed to sign in.",
                {
                    id: toastId,
                },
            );
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="flex min-h-screen items-center justify-center px-4 py-10">
            <Card className="w-full max-w-md">
                <CardHeader>
                    <CardTitle>Sign in to NoteMesh</CardTitle>
                    <CardDescription>
                        Use your email and password to access your workspace.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form
                        className="flex flex-col gap-4"
                        onSubmit={handleSubmit}
                    >
                        <div className="flex flex-col gap-1.5">
                            <Label htmlFor="email">Email</Label>
                            <Input
                                id="email"
                                type="email"
                                autoComplete="email"
                                value={email}
                                onChange={(event) =>
                                    setEmail(event.target.value)
                                }
                                placeholder="owner@example.com"
                                required
                                disabled={submitting}
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label htmlFor="password">Password</Label>
                            <Input
                                id="password"
                                type="password"
                                autoComplete="current-password"
                                value={password}
                                onChange={(event) =>
                                    setPassword(event.target.value)
                                }
                                placeholder="Enter your password"
                                required
                                disabled={submitting}
                            />
                        </div>
                        <Button type="submit" disabled={submitting}>
                            {submitting ? (
                                <Spinner size="sm" className="mr-2" />
                            ) : null}
                            {submitting ? "Signing in..." : "Sign in"}
                        </Button>
                    </form>

                    <p className="mt-4 text-sm text-muted-foreground">
                        First user setup?{" "}
                        <Link
                            className="text-primary underline"
                            href="/auth/bootstrap"
                        >
                            Bootstrap account
                        </Link>
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
