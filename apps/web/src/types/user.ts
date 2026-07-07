// src/types/user.ts

export type UserRole = 'admin' | 'user' | 'client';

export interface UserProfile {
  uid: string;
  email: string;
  name?: string;
  companyId?: string; // Links user to an organization tenant (e.g. 'cromex')
  role: UserRole;
  createdAt?: Date;
}

export interface Company {
  id: string; // matches companyId
  name: string;
  allowedTools: string[]; // List of tool slugs allowed for this company
  isActive: boolean;
}

export interface ToolInfo {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  isPrivate: boolean;
}
