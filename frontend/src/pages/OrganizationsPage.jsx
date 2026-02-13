import { useState, useEffect, useCallback } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, IconButton, List, ListItem,
  ListItemSecondaryAction, ListItemText, Stack, TextField, Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import PersonAddIcon from '@mui/icons-material/PersonAdd'
import api from '../services/api'

export default function OrganizationsPage() {
  const [orgs, setOrgs] = useState([])
  const [selected, setSelected] = useState(null)
  const [members, setMembers] = useState([])
  const [allUsers, setAllUsers] = useState([])
  const [createOpen, setCreateOpen] = useState(false)
  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [form, setForm] = useState({ name: '', slug: '' })
  const [memberUserId, setMemberUserId] = useState('')
  const [error, setError] = useState('')

  const fetchOrgs = useCallback(async () => {
    try {
      const { data } = await api.get('/organizations')
      setOrgs(data)
    } catch (_) {
      setError('Failed to load organizations')
    }
  }, [])

  const fetchUsers = useCallback(async () => {
    try {
      const { data } = await api.get('/users')
      setAllUsers(data)
    } catch (_) {}
  }, [])

  useEffect(() => {
    fetchOrgs()
    fetchUsers()
  }, [fetchOrgs, fetchUsers])

  const fetchMembers = useCallback(async (orgId) => {
    try {
      const { data } = await api.get(`/organizations/${orgId}/members`)
      setMembers(data)
    } catch (_) {}
  }, [])

  const selectOrg = (org) => {
    setSelected(org)
    fetchMembers(org.id)
  }

  const handleCreate = async () => {
    if (!form.name.trim()) return
    try {
      await api.post('/organizations', {
        name: form.name,
        slug: form.slug || undefined,
      })
      setCreateOpen(false)
      setForm({ name: '', slug: '' })
      fetchOrgs()
    } catch (e) {
      setError(e.response?.data?.detail || 'Create failed')
    }
  }

  const handleDeleteOrg = async (orgId) => {
    if (!confirm('Deactivate this organization?')) return
    try {
      await api.delete(`/organizations/${orgId}`)
      if (selected?.id === orgId) setSelected(null)
      fetchOrgs()
    } catch (e) {
      setError(e.response?.data?.detail || 'Delete failed')
    }
  }

  const handleAddMember = async () => {
    if (!memberUserId || !selected) return
    try {
      await api.post(`/organizations/${selected.id}/members`, { user_id: memberUserId })
      setAddMemberOpen(false)
      setMemberUserId('')
      fetchMembers(selected.id)
      fetchOrgs()
    } catch (e) {
      setError(e.response?.data?.detail || 'Add member failed')
    }
  }

  const handleRemoveMember = async (userId) => {
    if (!selected) return
    try {
      await api.delete(`/organizations/${selected.id}/members/${userId}`)
      fetchMembers(selected.id)
      fetchOrgs()
    } catch (_) {}
  }

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h5" fontWeight={600}>Organizations</Typography>
          <Typography variant="body2" color="text.secondary">
            Manage workspaces and team members
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          New Org
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      <Stack direction="row" spacing={3} alignItems="flex-start">
        {/* Org list */}
        <Box sx={{ minWidth: 260 }}>
          {orgs.length === 0 && (
            <Typography color="text.secondary" variant="body2">No organizations yet.</Typography>
          )}
          {orgs.map((org) => (
            <Card
              key={org.id}
              onClick={() => selectOrg(org)}
              sx={{
                mb: 1, cursor: 'pointer',
                border: selected?.id === org.id ? 2 : 1,
                borderColor: selected?.id === org.id ? 'primary.main' : 'divider',
              }}
            >
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography fontWeight={500}>{org.name}</Typography>
                      {!org.active && <Chip label="inactive" size="small" color="error" />}
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      /{org.slug} · {org.member_count} member{org.member_count !== 1 ? 's' : ''}
                    </Typography>
                  </Box>
                  {org.slug !== 'default' && (
                    <IconButton
                      size="small"
                      onClick={(e) => { e.stopPropagation(); handleDeleteOrg(org.id) }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>

        {/* Members panel */}
        {selected && (
          <Box flex={1}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">{selected.name} — Members</Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<PersonAddIcon />}
                onClick={() => setAddMemberOpen(true)}
              >
                Add member
              </Button>
            </Stack>

            {members.length === 0 ? (
              <Typography color="text.secondary" variant="body2">No members yet.</Typography>
            ) : (
              <List dense>
                {members.map((m) => (
                  <ListItem key={m.id} divider>
                    <ListItemText
                      primary={m.username}
                      secondary={m.role}
                    />
                    <ListItemSecondaryAction>
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => handleRemoveMember(m.id)}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        )}
      </Stack>

      {/* Create org dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Organization</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name" fullWidth required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              label="Slug (optional)" fullWidth
              placeholder="my-org"
              helperText="Lowercase letters, numbers, dashes"
              value={form.slug}
              onChange={(e) => setForm({ ...form, slug: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate}>Create</Button>
        </DialogActions>
      </Dialog>

      {/* Add member dialog */}
      <Dialog open={addMemberOpen} onClose={() => setAddMemberOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Member to {selected?.name}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              select label="User" fullWidth SelectProps={{ native: true }}
              value={memberUserId}
              onChange={(e) => setMemberUserId(e.target.value)}
            >
              <option value="">— select user —</option>
              {allUsers.map((u) => (
                <option key={u.id} value={u.id}>{u.username} ({u.role})</option>
              ))}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddMemberOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleAddMember} disabled={!memberUserId}>
            Add
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
