const DEFAULT_TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID || null;

export const dbPaths = {
  sessions: (tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/sessions` : `csm_sessions`,
    
  sessionDoc: (id: string, tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/sessions/${id}` : `csm_sessions/${id}`,
    
  articles: (tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/articles` : `articles`,
    
  articleDoc: (id: string, tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/articles/${id}` : `articles/${id}`,
    
  configs: (tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/agent_configurations` : `agent_configurations`,
    
  configDoc: (agentName: string, tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/agent_configurations/${agentName}` : `agent_configurations/${agentName}`,
    
  apiKeysDoc: (tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/api_keys/keys` : `agent_configurations/api_keys`,
    
  socialQueue: (tenantId: string | null = DEFAULT_TENANT_ID) => 
    tenantId ? `tenants/${tenantId}/social_queue` : `social_queue`,
    
  socialQueueDoc: (id: string, tenantId: string | null = DEFAULT_TENANT_ID) =>
    tenantId ? `tenants/${tenantId}/social_queue/${id}` : `social_queue/${id}`,

  usageLogs: (tenantId: string | null = DEFAULT_TENANT_ID) =>
    tenantId ? `tenants/${tenantId}/usage_logs` : `usage_logs`,

  videoTemplates: (tenantId: string | null = DEFAULT_TENANT_ID) =>
    tenantId ? `tenants/${tenantId}/video_templates` : `video_templates`,

  videoTemplateDoc: (id: string, tenantId: string | null = DEFAULT_TENANT_ID) =>
    tenantId ? `tenants/${tenantId}/video_templates/${id}` : `video_templates/${id}`,

  avatarsDoc: (tenantId: string | null = DEFAULT_TENANT_ID) =>
    tenantId ? `tenants/${tenantId}/agent_configurations/avatars` : `agent_configurations/avatars`,
};
