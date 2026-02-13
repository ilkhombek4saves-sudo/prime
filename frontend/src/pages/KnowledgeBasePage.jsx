import { useState, useEffect, useCallback } from 'react'
import {
  Box, Button, Card, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, IconButton, LinearProgress,
  List, ListItem, ListItemSecondaryAction, ListItemText, MenuItem,
  Select, Stack, TextField, Tooltip, Typography, Alert,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import SearchIcon from '@mui/icons-material/Search'
import RefreshIcon from '@mui/icons-material/Refresh'
import api from '../services/api'

const STATUS_COLOR = {
  pending: 'warning',
  indexing: 'info',
  indexed: 'success',
  failed: 'error',
}

export default function KnowledgeBasePage() {
  const [kbs, setKbs] = useState([])
  const [agents, setAgents] = useState([])
  const [selected, setSelected] = useState(null)
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', agent_id: '' })
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [error, setError] = useState('')

  const fetchKbs = useCallback(async () => {
    try {
      const { data } = await api.get('/knowledge-bases')
      setKbs(data)
    } catch (e) {
      setError('Failed to load knowledge bases')
    }
  }, [])

  const fetchAgents = useCallback(async () => {
    try {
      const { data } = await api.get('/agents')
      setAgents(data)
    } catch (_) {}
  }, [])

  useEffect(() => {
    fetchKbs()
    fetchAgents()
  }, [fetchKbs, fetchAgents])

  const fetchDocs = useCallback(async (kbId) => {
    try {
      const { data } = await api.get(`/knowledge-bases/${kbId}/documents`)
      setDocs(data)
    } catch (_) {}
  }, [])

  const selectKb = (kb) => {
    setSelected(kb)
    fetchDocs(kb.id)
  }

  const handleCreate = async () => {
    if (!form.name.trim()) return
    try {
      await api.post('/knowledge-bases', {
        name: form.name,
        description: form.description,
        agent_id: form.agent_id || null,
      })
      setCreateOpen(false)
      setForm({ name: '', description: '', agent_id: '' })
      fetchKbs()
    } catch (e) {
      setError(e.response?.data?.detail || 'Create failed')
    }
  }

  const handleDelete = async (kbId) => {
    if (!confirm('Delete this knowledge base and all documents?')) return
    try {
      await api.delete(`/knowledge-bases/${kbId}`)
      if (selected?.id === kbId) setSelected(null)
      fetchKbs()
    } catch (e) {
      setError('Delete failed')
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !selected) return
    setLoading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      await api.post(`/knowledge-bases/${selected.id}/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      fetchDocs(selected.id)
      fetchKbs()
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

  const handleDeleteDoc = async (docId) => {
    if (!confirm('Delete this document?')) return
    try {
      await api.delete(`/knowledge-bases/${selected.id}/documents/${docId}`)
      fetchDocs(selected.id)
      fetchKbs()
    } catch (_) {}
  }

  const handleSearch = async () => {
    if (!searchQuery.trim() || !selected) return
    try {
      const { data } = await api.post(`/knowledge-bases/${selected.id}/search`, {
        query: searchQuery, top_k: 5,
      })
      setSearchResults(data.results || [])
    } catch (e) {
      setError('Search failed')
    }
  }

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={600}>Knowledge Bases</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          New KB
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      <Stack direction="row" spacing={3} alignItems="flex-start">
        {/* KB List */}
        <Box sx={{ minWidth: 280 }}>
          {kbs.length === 0 && (
            <Typography color="text.secondary" variant="body2">
              No knowledge bases yet. Create one to enable RAG for your agents.
            </Typography>
          )}
          {kbs.map((kb) => (
            <Card
              key={kb.id}
              onClick={() => selectKb(kb)}
              sx={{
                mb: 1, cursor: 'pointer',
                border: selected?.id === kb.id ? 2 : 1,
                borderColor: selected?.id === kb.id ? 'primary.main' : 'divider',
              }}
            >
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography fontWeight={500}>{kb.name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {kb.document_count} document{kb.document_count !== 1 ? 's' : ''}
                      {kb.agent_id && ' · linked to agent'}
                    </Typography>
                  </Box>
                  <IconButton size="small" onClick={(e) => { e.stopPropagation(); handleDelete(kb.id) }}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>

        {/* Document panel */}
        {selected && (
          <Box flex={1}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">{selected.name}</Typography>
              <Stack direction="row" spacing={1}>
                <Tooltip title="Test search">
                  <IconButton onClick={() => setSearchOpen(true)}><SearchIcon /></IconButton>
                </Tooltip>
                <Tooltip title="Refresh">
                  <IconButton onClick={() => fetchDocs(selected.id)}><RefreshIcon /></IconButton>
                </Tooltip>
                <Button
                  variant="outlined"
                  startIcon={<UploadFileIcon />}
                  component="label"
                  disabled={loading}
                >
                  Upload
                  <input type="file" hidden accept=".pdf,.docx,.txt,.md,.csv" onChange={handleUpload} />
                </Button>
              </Stack>
            </Stack>

            {loading && <LinearProgress sx={{ mb: 1 }} />}

            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              Supported: PDF, DOCX, TXT, Markdown · Max 20MB · Indexing is automatic
            </Typography>

            {docs.length === 0 ? (
              <Typography color="text.secondary" variant="body2">
                No documents yet. Upload files to start indexing.
              </Typography>
            ) : (
              <List dense>
                {docs.map((doc) => (
                  <ListItem key={doc.id} divider>
                    <ListItemText
                      primary={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <span>{doc.filename}</span>
                          <Chip
                            label={doc.status}
                            size="small"
                            color={STATUS_COLOR[doc.status] || 'default'}
                          />
                        </Stack>
                      }
                      secondary={
                        doc.status === 'indexed'
                          ? `${doc.chunk_count} chunks · ${(doc.size_bytes / 1024).toFixed(1)} KB`
                          : doc.error || `${(doc.size_bytes / 1024).toFixed(1)} KB`
                      }
                    />
                    <ListItemSecondaryAction>
                      <IconButton edge="end" size="small" onClick={() => handleDeleteDoc(doc.id)}>
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

      {/* Create KB dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Knowledge Base</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name" fullWidth required
              value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              label="Description" fullWidth multiline rows={2}
              value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <Select
              displayEmpty value={form.agent_id}
              onChange={(e) => setForm({ ...form, agent_id: e.target.value })}
            >
              <MenuItem value=""><em>No agent (shared)</em></MenuItem>
              {agents.map((a) => (
                <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>
              ))}
            </Select>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate}>Create</Button>
        </DialogActions>
      </Dialog>

      {/* Search test dialog */}
      <Dialog open={searchOpen} onClose={() => { setSearchOpen(false); setSearchResults([]) }} maxWidth="md" fullWidth>
        <DialogTitle>Test Search — {selected?.name}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Stack direction="row" spacing={1}>
              <TextField
                label="Query" fullWidth
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
              <Button variant="contained" onClick={handleSearch}>Search</Button>
            </Stack>
            {searchResults.map((r, i) => (
              <Card key={i} variant="outlined">
                <CardContent>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" color="text.secondary">
                      {r.filename} · chunk {r.chunk_index}
                    </Typography>
                    <Chip label={`score: ${r.score}`} size="small" />
                  </Stack>
                  <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12 }}>
                    {r.content}
                  </Typography>
                </CardContent>
              </Card>
            ))}
            {searchResults.length === 0 && searchQuery && (
              <Typography color="text.secondary">No results found.</Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setSearchOpen(false); setSearchResults([]) }}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
