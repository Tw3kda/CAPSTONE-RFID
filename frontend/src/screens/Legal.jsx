import { Shell } from '../components.jsx'
import { Link } from '../router.jsx'
import { PrivacyContent, TermsContent } from './legal-content.jsx'

export function LegalFooter() {
  return <footer className="access-footer container"><nav aria-label="Información legal"><Link to="/terminos">Términos y condiciones</Link><span aria-hidden="true">|</span><Link to="/privacidad">Política de privacidad</Link></nav></footer>
}

export function Legal({ privacy }) {
  return <Shell sinNav><div className="container content legal-page"><Link to="/acceso" className="enlace">Volver al acceso</Link><article className="legal-document">{privacy ? <PrivacyContent /> : <TermsContent />}</article></div></Shell>
}
