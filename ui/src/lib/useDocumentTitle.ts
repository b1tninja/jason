import { useEffect } from "react";

/** Sets the page's title while the calling screen is shown (WCAG 2.4.2), and puts the title it found back when the screen goes. The console's name
 * follows the screen's, so "Split document: Draft - jason" tells a screen reader where it is. A title never carries a file name. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    if (typeof document === "undefined") return;
    const was = document.title;
    document.title = `${title} - jason`;
    return () => { document.title = was; };
  }, [title]);
}
