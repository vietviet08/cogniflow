"use client";

import { useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Building2, Plus, Trash2, ShieldAlert } from "lucide-react";

import {
  createOrganization,
  listOrganizationMembers,
  addOrganizationMember,
  updateOrganizationMember,
  removeOrganizationMember,
} from "@/lib/api/client";
import { useOrganization } from "@/components/organization-provider";
import { useAuth } from "@/components/auth-provider";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

type SubmitEvent = { preventDefault: () => void };

type OrganizationMember = {
  membership_id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: string;
  joined_at: string | null;
};

interface WorkspaceCardProps {
  organizationsLoading: boolean;
  organizations: Array<{ id: string; name: string; role?: string }>;
  activeOrganizationId: string | null;
  organizationName: string;
  creatingOrganization: boolean;
  onOrganizationNameChange: (value: string) => void;
  onSelectOrganization: (organizationId: string) => void;
  onCreateOrganization: (event: SubmitEvent) => void;
}

function WorkspaceCard(props: Readonly<WorkspaceCardProps>) {
  const {
    organizationsLoading,
    organizations,
    activeOrganizationId,
    organizationName,
    creatingOrganization,
    onOrganizationNameChange,
    onSelectOrganization,
    onCreateOrganization,
  } = props;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Building2 className="h-4 w-4 text-primary" />
          Organizations
        </CardTitle>
        <CardDescription>
          Create organizations and switch active workspace.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {organizationsLoading ? (
          <div className="flex justify-center py-4">
            <Spinner />
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {organizations.map((org) => {
              const isActive = activeOrganizationId === org.id;
              return (
                <Button
                  key={org.id}
                  type="button"
                  variant={isActive ? "default" : "outline"}
                  size="sm"
                  onClick={() => onSelectOrganization(org.id)}
                  className="gap-2"
                >
                  <span>{org.name}</span>
                  {org.role ? (
                    <Badge variant={isActive ? "secondary" : "outline"}>
                      {org.role}
                    </Badge>
                  ) : null}
                </Button>
              );
            })}
            {organizations.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                You have no organizations yet.
              </p>
            ) : null}
          </div>
        )}

        <form
          onSubmit={onCreateOrganization}
          className="flex flex-col gap-3 md:flex-row md:items-end"
        >
          <div className="flex-1">
            <Label htmlFor="organization-name">New organization</Label>
            <Input
              id="organization-name"
              value={organizationName}
              onChange={(e) => onOrganizationNameChange(e.target.value)}
              placeholder="e.g. Revenue Intelligence Team"
              disabled={creatingOrganization}
              required
            />
          </div>
          <Button
            type="submit"
            disabled={creatingOrganization || !organizationName.trim()}
            className="gap-2"
          >
            {creatingOrganization ? (
              <Spinner size="sm" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            {creatingOrganization ? "Creating..." : "Create Organization"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

interface MembersCardProps {
  activeOrganizationName: string;
  isAdmin: boolean;
  isOwner: boolean;
  currentUserId?: string;
  members: OrganizationMember[];
  membersLoading: boolean;
  email: string;
  role: string;
  submitting: boolean;
  updatingId: string | null;
  onEmailChange: (value: string) => void;
  onRoleChange: (value: string) => void;
  onAddMember: (event: SubmitEvent) => void;
  onUpdateRole: (userId: string, role: string) => void;
  onRemoveMember: (userId: string, userName: string) => void;
}

function MembersCard(props: Readonly<MembersCardProps>) {
  const {
    activeOrganizationName,
    isAdmin,
    isOwner,
    currentUserId,
    members,
    membersLoading,
    email,
    role,
    submitting,
    updatingId,
    onEmailChange,
    onRoleChange,
    onAddMember,
    onUpdateRole,
    onRemoveMember,
  } = props;

  let membersContent: ReactNode;
  if (!isAdmin) {
    membersContent = (
      <p className="text-sm text-muted-foreground">
        You are currently a member. Only organization admin or owner can view
        and manage member list.
      </p>
    );
  } else if (membersLoading) {
    membersContent = (
      <div className="flex justify-center py-6">
        <Spinner />
      </div>
    );
  } else {
    membersContent = (
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((member) => {
              const isSelf = member.user_id === currentUserId;
              const isRemoving = updatingId === `remove-${member.user_id}`;
              const isUpdating = updatingId === `update-${member.user_id}`;
              const canModifyOwner = isOwner || member.role !== "owner";

              return (
                <TableRow key={member.membership_id}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium flex items-center gap-2">
                        {member.display_name}
                        {isSelf ? (
                          <Badge variant="outline" className="text-[10px]">
                            You
                          </Badge>
                        ) : null}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {member.email}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {isSelf || !canModifyOwner ? (
                      <Badge
                        variant={
                          member.role === "owner" ? "default" : "secondary"
                        }
                      >
                        {member.role}
                      </Badge>
                    ) : (
                      <Select
                        value={member.role}
                        onValueChange={(value) =>
                          onUpdateRole(member.user_id, value)
                        }
                        disabled={isUpdating || isRemoving}
                      >
                        <SelectTrigger className="h-8 w-[120px] border-0 bg-muted/50 px-2 py-1 text-xs shadow-none">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="member">Member</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                          {isOwner ? (
                            <SelectItem value="owner">Owner</SelectItem>
                          ) : null}
                        </SelectContent>
                      </Select>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {member.joined_at
                      ? new Date(member.joined_at).toLocaleDateString()
                      : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    {!isSelf && canModifyOwner ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={isUpdating || isRemoving}
                        onClick={() =>
                          onRemoveMember(member.user_id, member.display_name)
                        }
                        className="h-8 w-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                        title="Remove from organization"
                      >
                        {isRemoving ? (
                          <Spinner size="sm" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
            {members.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center py-6 text-muted-foreground text-sm"
                >
                  No members found.
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-primary" />
          Organization Members: {activeOrganizationName}
        </CardTitle>
        <CardDescription>
          Manage who has access to this organization's projects and resources.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isAdmin ? (
          <form
            onSubmit={onAddMember}
            className="flex flex-col gap-3 md:flex-row md:items-end"
          >
            <div className="flex-1">
              <Label htmlFor="member-email">Email Address</Label>
              <Input
                id="member-email"
                type="email"
                required
                value={email}
                onChange={(e) => onEmailChange(e.target.value)}
                placeholder="Enter user's email"
                disabled={submitting}
              />
            </div>
            <div className="w-40">
              <Label htmlFor="member-role">Role</Label>
              <Select
                value={role}
                onValueChange={onRoleChange}
                disabled={submitting}
              >
                <SelectTrigger id="member-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                  {isOwner ? (
                    <SelectItem value="owner">Owner</SelectItem>
                  ) : null}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={submitting} className="gap-2">
              {submitting ? (
                <Spinner size="sm" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {submitting ? "Adding..." : "Add Member"}
            </Button>
          </form>
        ) : null}
        {membersContent}
      </CardContent>
    </Card>
  );
}

export function OrganizationSettings() {
  const { user } = useAuth();
  const {
    organizations,
    activeOrganization,
    isLoading: organizationsLoading,
    setActiveOrganizationId,
  } = useOrganization();
  const queryClient = useQueryClient();

  const [organizationName, setOrganizationName] = useState("");
  const [creatingOrganization, setCreatingOrganization] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [submitting, setSubmitting] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const activeOrganizationRole = (
    activeOrganization?.role ?? "member"
  ).toLowerCase();
  const isAdmin =
    activeOrganizationRole === "admin" || activeOrganizationRole === "owner";
  const isOwner = activeOrganizationRole === "owner";

  const { data: membersData, isLoading: membersLoading } = useQuery({
    queryKey: ["org-members", activeOrganization?.id],
    queryFn: () => listOrganizationMembers(activeOrganization!.id),
    enabled: Boolean(activeOrganization?.id && isAdmin),
  });

  const members = membersData?.data.items || [];

  async function handleCreateOrganization(event: SubmitEvent) {
    event.preventDefault();
    const name = organizationName.trim();
    if (!name) return;

    setCreatingOrganization(true);
    const toastId = toast.loading("Creating organization...");
    try {
      const response = await createOrganization({ name });
      await queryClient.invalidateQueries({
        queryKey: ["organizations"],
      });
      setActiveOrganizationId(response.data.id);
      setOrganizationName("");
      toast.success("Organization created.", { id: toastId });
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to create organization.",
        { id: toastId },
      );
    } finally {
      setCreatingOrganization(false);
    }
  }

  async function handleAddMember(e: SubmitEvent) {
    e.preventDefault();
    if (!activeOrganization) return;

    setSubmitting(true);
    const toastId = toast.loading("Adding member...");
    try {
      await addOrganizationMember(activeOrganization.id, email, role);
      await queryClient.invalidateQueries({
        queryKey: ["org-members", activeOrganization.id],
      });
      setEmail("");
      setRole("member");
      toast.success("Member added successfully.", { id: toastId });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to add member.",
        { id: toastId },
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemoveMember(userId: string, userName: string) {
    if (!activeOrganization) return;
    if (
      !confirm(
        `Are you sure you want to remove ${userName} from the organization?`,
      )
    )
      return;

    setUpdatingId(`remove-${userId}`);
    const toastId = toast.loading("Removing member...");
    try {
      await removeOrganizationMember(activeOrganization.id, userId);
      await queryClient.invalidateQueries({
        queryKey: ["org-members", activeOrganization.id],
      });
      toast.success("Member removed.", { id: toastId });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to remove member.",
        { id: toastId },
      );
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
      await queryClient.invalidateQueries({
        queryKey: ["org-members", activeOrganization.id],
      });
      toast.success("Role updated.", { id: toastId });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to update role.",
        { id: toastId },
      );
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="space-y-6 mx-6 mt-4">
      <WorkspaceCard
        organizationsLoading={organizationsLoading}
        organizations={organizations}
        activeOrganizationId={activeOrganization?.id ?? null}
        organizationName={organizationName}
        creatingOrganization={creatingOrganization}
        onOrganizationNameChange={setOrganizationName}
        onSelectOrganization={setActiveOrganizationId}
        onCreateOrganization={handleCreateOrganization}
      />

      {activeOrganization ? (
        <MembersCard
          activeOrganizationName={activeOrganization.name}
          isAdmin={isAdmin}
          isOwner={isOwner}
          currentUserId={user?.id}
          members={members}
          membersLoading={membersLoading}
          email={email}
          role={role}
          submitting={submitting}
          updatingId={updatingId}
          onEmailChange={setEmail}
          onRoleChange={setRole}
          onAddMember={handleAddMember}
          onUpdateRole={handleUpdateRole}
          onRemoveMember={handleRemoveMember}
        />
      ) : null}
    </div>
  );
}
