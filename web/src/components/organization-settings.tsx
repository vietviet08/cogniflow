"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Plus, Trash2, ShieldAlert } from "lucide-react";

import {
    listOrganizationMembers,
    addOrganizationMember,
    updateOrganizationMember,
    removeOrganizationMember,
} from "@/lib/api/client";
import { useOrganization } from "@/components/organization-provider";
import { useAuth } from "@/components/auth-provider";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export function OrganizationSettings() {
    const { user } = useAuth();
    const { activeOrganization } = useOrganization();
    const queryClient = useQueryClient();

    const [email, setEmail] = useState("");
    const [role, setRole] = useState("member");
    const [submitting, setSubmitting] = useState(false);
    const [updatingId, setUpdatingId] = useState<string | null>(null);

    const { data: membersData, isLoading } = useQuery({
        queryKey: ["org-members", activeOrganization?.id],
        queryFn: () => listOrganizationMembers(activeOrganization!.id),
        enabled: Boolean(activeOrganization?.id),
    });

    const members = membersData?.data.items || [];
    
    // Check current user's role in the organization
    const myMembership = members.find(m => m.user_id === user?.id);
    const myRole = myMembership?.role || activeOrganization?.role;
    const isAdmin = myRole === "admin" || myRole === "owner";
    const isOwner = myRole === "owner";

    async function handleAddMember(e: React.FormEvent) {
        e.preventDefault();
        if (!activeOrganization) return;
        
        setSubmitting(true);
        const toastId = toast.loading("Adding member...");
        try {
            await addOrganizationMember(activeOrganization.id, email, role);
            await queryClient.invalidateQueries({ queryKey: ["org-members", activeOrganization.id] });
            setEmail("");
            setRole("member");
            toast.success("Member added successfully.", { id: toastId });
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to add member.", { id: toastId });
        } finally {
            setSubmitting(false);
        }
    }

    async function handleRemoveMember(userId: string, userName: string) {
        if (!activeOrganization) return;
        if (!confirm(`Are you sure you want to remove ${userName} from the organization?`)) return;
        
        setUpdatingId(`remove-${userId}`);
        const toastId = toast.loading("Removing member...");
        try {
            await removeOrganizationMember(activeOrganization.id, userId);
            await queryClient.invalidateQueries({ queryKey: ["org-members", activeOrganization.id] });
            toast.success("Member removed.", { id: toastId });
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to remove member.", { id: toastId });
        } finally {
            setUpdatingId(null);
        }
    }

    async function handleUpdateRole(userId: string, newRole: string) {
        if (!activeOrganization) return;
        
        setUpdatingId(`update-${userId}`);
        const toastId = toast.loading("Updating role...");
        try {
            await updateOrganizationMember(activeOrganization.id, userId, newRole);
            await queryClient.invalidateQueries({ queryKey: ["org-members", activeOrganization.id] });
            toast.success("Role updated.", { id: toastId });
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to update role.", { id: toastId });
        } finally {
            setUpdatingId(null);
        }
    }

    if (!activeOrganization) {
        return null;
    }

    return (
        <Card className="mb-6">
            <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-primary" />
                    Organization Members: {activeOrganization.name}
                </CardTitle>
                <CardDescription>
                    Manage who has access to this organization's projects and resources.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {isAdmin && (
                    <form onSubmit={handleAddMember} className="flex flex-col gap-3 md:flex-row md:items-end">
                        <div className="flex-1">
                            <Label htmlFor="member-email">Email Address</Label>
                            <Input
                                id="member-email"
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="Enter user's email"
                                disabled={submitting}
                            />
                        </div>
                        <div className="w-40">
                            <Label htmlFor="member-role">Role</Label>
                            <select
                                id="member-role"
                                value={role}
                                onChange={(e) => setRole(e.target.value)}
                                disabled={submitting}
                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                                {isOwner && <option value="owner">Owner</option>}
                            </select>
                        </div>
                        <Button type="submit" disabled={submitting} className="gap-2">
                            {submitting ? <Spinner size="sm" /> : <Plus className="h-4 w-4" />}
                            {submitting ? "Adding..." : "Add Member"}
                        </Button>
                    </form>
                )}

                {isLoading ? (
                    <div className="flex justify-center py-6">
                        <Spinner />
                    </div>
                ) : (
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>User</TableHead>
                                    <TableHead>Role</TableHead>
                                    <TableHead>Joined</TableHead>
                                    {isAdmin && <TableHead className="text-right">Actions</TableHead>}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {members.map((member) => {
                                    const isSelf = member.user_id === user?.id;
                                    const isRemoving = updatingId === `remove-${member.user_id}`;
                                    const isUpdating = updatingId === `update-${member.user_id}`;
                                    
                                    return (
                                        <TableRow key={member.membership_id}>
                                            <TableCell>
                                                <div className="flex flex-col">
                                                    <span className="font-medium flex items-center gap-2">
                                                        {member.display_name}
                                                        {isSelf && <Badge variant="outline" className="text-[10px]">You</Badge>}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground">{member.email}</span>
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                {isAdmin && !isSelf && (isOwner || member.role !== "owner") ? (
                                                    <select
                                                        value={member.role}
                                                        onChange={(e) => handleUpdateRole(member.user_id, e.target.value)}
                                                        disabled={isUpdating || isRemoving}
                                                        className="h-8 rounded-md border-0 bg-muted/50 px-2 py-1 text-xs"
                                                    >
                                                        <option value="member">Member</option>
                                                        <option value="admin">Admin</option>
                                                        {isOwner && <option value="owner">Owner</option>}
                                                    </select>
                                                ) : (
                                                    <Badge variant={member.role === "owner" ? "default" : "secondary"}>
                                                        {member.role}
                                                    </Badge>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-xs text-muted-foreground">
                                                {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : "-"}
                                            </TableCell>
                                            {isAdmin && (
                                                <TableCell className="text-right">
                                                    {!isSelf && (isOwner || member.role !== "owner") && (
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            disabled={isUpdating || isRemoving}
                                                            onClick={() => handleRemoveMember(member.user_id, member.display_name)}
                                                            className="h-8 w-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                                                            title="Remove from organization"
                                                        >
                                                            {isRemoving ? <Spinner size="sm" /> : <Trash2 className="h-4 w-4" />}
                                                        </Button>
                                                    )}
                                                </TableCell>
                                            )}
                                        </TableRow>
                                    );
                                })}
                                {members.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={isAdmin ? 4 : 3} className="text-center py-6 text-muted-foreground text-sm">
                                            No members found.
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
