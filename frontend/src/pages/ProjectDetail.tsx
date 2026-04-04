import { useParams } from 'react-router-dom'

function ProjectDetail() {
  const { id } = useParams()
  return (
    <div style={{ padding: '2rem' }}>
      <h1>Project {id}</h1>
      <p>Project details coming soon.</p>
    </div>
  )
}

export default ProjectDetail
