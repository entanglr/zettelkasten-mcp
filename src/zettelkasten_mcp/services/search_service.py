"""Service for searching and discovering notes in the Zettelkasten."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from sqlalchemy import select, text

from zettelkasten_mcp.models.schema import (
    BatchOperationResult, BatchResult, Note, NoteType
)

from zettelkasten_mcp.services.zettel_service import ZettelService

from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from zettelkasten_mcp.models.db_models import DBLink, DBNote

@dataclass
class SearchResult:
    """A search result with a note and its relevance score."""
    note: Note
    score: float
    matched_terms: Set[str]
    matched_context: str

class SearchService:
    """Service for searching notes in the Zettelkasten."""
    
    def __init__(self, zettel_service: Optional[ZettelService] = None):
        """Initialize the search service."""
        self.zettel_service = zettel_service or ZettelService()
    
    def initialize(self) -> None:
        """Initialize the service and dependencies."""
        # Initialize the zettel service if it hasn't been initialized
        self.zettel_service.initialize()
    
    def search_by_text(
        self, query: str, include_content: bool = True, include_title: bool = True
    ) -> List[SearchResult]:
        """Search for notes by text content."""
        if not query:
            return []
        
        # Normalize query
        query = query.lower()
        query_terms = set(query.split())
        
        # Get all notes
        all_notes = self.zettel_service.get_all_notes()
        results = []
        
        for note in all_notes:
            score = 0.0
            matched_terms: Set[str] = set()
            matched_context = ""
            
            # Check title
            if include_title and note.title:
                title_lower = note.title.lower()
                # Exact match in title is highest score
                if query in title_lower:
                    score += 2.0
                    matched_context = f"Title: {note.title}"
                # Check for term matches in title
                for term in query_terms:
                    if term in title_lower:
                        score += 0.5
                        matched_terms.add(term)
            
            # Check content
            if include_content and note.content:
                content_lower = note.content.lower()
                # Exact match in content
                if query in content_lower:
                    score += 1.0
                    # Extract a snippet around the match
                    index = content_lower.find(query)
                    start = max(0, index - 40)
                    end = min(len(content_lower), index + len(query) + 40)
                    snippet = note.content[start:end]
                    matched_context = f"Content: ...{snippet}..."
                # Check for term matches in content
                for term in query_terms:
                    if term in content_lower:
                        score += 0.2
                        matched_terms.add(term)
            
            # Add to results if score is positive
            if score > 0:
                results.append(
                    SearchResult(
                        note=note,
                        score=score,
                        matched_terms=matched_terms,
                        matched_context=matched_context
                    )
                )
        
        # Sort by score (descending)
        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    def search_by_tag(self, tags: Union[str, List[str]]) -> List[Note]:
        """Search for notes by tags."""
        if isinstance(tags, str):
            return self.zettel_service.get_notes_by_tag(tags)
        else:
            # If we have multiple tags, find notes with any of the tags
            all_matching_notes = []
            for tag in tags:
                notes = self.zettel_service.get_notes_by_tag(tag)
                all_matching_notes.extend(notes)
            # Remove duplicates by converting to a dictionary by ID
            unique_notes = {note.id: note for note in all_matching_notes}
            return list(unique_notes.values())
    
    def search_by_link(self, note_id: str, direction: str = "both") -> List[Note]:
        """Search for notes linked to/from a note."""
        return self.zettel_service.get_linked_notes(note_id, direction)
    
    def find_orphaned_notes(self) -> List[Note]:
        """Find notes with no incoming or outgoing links."""
        orphans = []
        
        with self.zettel_service.repository.session_factory() as session:
            # Subquery for notes with links
            notes_with_links = (
                select(DBNote.id)
                .outerjoin(DBLink, or_(
                    DBNote.id == DBLink.source_id,
                    DBNote.id == DBLink.target_id
                ))
                .where(or_(
                    DBLink.source_id != None,
                    DBLink.target_id != None
                ))
                .subquery()
            )
            
            # Query for notes without links
            query = (
                select(DBNote)
                .options(
                    joinedload(DBNote.tags),
                    joinedload(DBNote.outgoing_links),
                    joinedload(DBNote.incoming_links)
                )
                .where(DBNote.id.not_in(select(notes_with_links)))
            )
            
            result = session.execute(query)
            orphaned_db_notes = result.unique().scalars().all()
            
            # Convert DB notes to model Notes
            for db_note in orphaned_db_notes:
                note = self.zettel_service.get_note(db_note.id)
                if note:
                    orphans.append(note)
                    
        return orphans
    
    def find_central_notes(self, limit: int = 10) -> List[Tuple[Note, int]]:
        """Find notes with the most connections (incoming + outgoing links)."""
        note_connections = []
        # Direct database query to count connections for all notes at once
        with self.zettel_service.repository.session_factory() as session:
            # Use a CTE for better readability and performance
            query = text("""
            WITH outgoing AS (
                SELECT source_id as note_id, COUNT(*) as outgoing_count 
                FROM links 
                GROUP BY source_id
            ),
            incoming AS (
                SELECT target_id as note_id, COUNT(*) as incoming_count 
                FROM links 
                GROUP BY target_id
            )
            SELECT n.id,
                COALESCE(o.outgoing_count, 0) as outgoing,
                COALESCE(i.incoming_count, 0) as incoming,
                (COALESCE(o.outgoing_count, 0) + COALESCE(i.incoming_count, 0)) as total
            FROM notes n
            LEFT JOIN outgoing o ON n.id = o.note_id
            LEFT JOIN incoming i ON n.id = i.note_id
            WHERE (COALESCE(o.outgoing_count, 0) + COALESCE(i.incoming_count, 0)) > 0
            ORDER BY total DESC
            LIMIT :limit
            """)
            
            results = session.execute(query, {"limit": limit}).all()
            
            # Process results
            for note_id, outgoing_count, incoming_count, total_connections in results:
                total_connections = outgoing_count + incoming_count
                if total_connections > 0:  # Only include notes with connections
                    note = self.zettel_service.get_note(note_id)
                    if note:
                        note_connections.append((note, total_connections))
        
        # Sort by total connections (descending)
        note_connections.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N notes
        return note_connections[:limit]
    
    def find_notes_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_updated: bool = False
    ) -> List[Note]:
        """Find notes created or updated within a date range."""
        all_notes = self.zettel_service.get_all_notes()
        matching_notes = []
        
        for note in all_notes:
            # Get the relevant date
            date = note.updated_at if use_updated else note.created_at
            
            # Check if in range
            if start_date and date < start_date:
                continue
            if end_date and date >= end_date + datetime.timedelta(seconds=1):
                continue
            
            matching_notes.append(note)
        
        # Sort by date (descending)
        matching_notes.sort(
            key=lambda x: x.updated_at if use_updated else x.created_at,
            reverse=True
        )
        
        return matching_notes
    
    def find_similar_notes(self, note_id: str, threshold: float = 0.5) -> List[Tuple[Note, float]]:
        """Find notes similar to the given note based on shared tags and links.
        
        Args:
            note_id: ID of the reference note
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            List of tuples containing (note, similarity_score)
        """
        return self.zettel_service.find_similar_notes(note_id, threshold)
    
    def search_combined(
        self,
        text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        note_type: Optional[NoteType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[SearchResult]:
        """Perform a combined search with multiple criteria."""
        # Start with all notes
        all_notes = self.zettel_service.get_all_notes()
        
        # Filter by criteria
        filtered_notes = []
        for note in all_notes:
            # Check note type
            if note_type and note.note_type != note_type:
                continue
            
            # Check date range
            if start_date and note.created_at < start_date:
                continue
            if end_date and note.created_at > end_date:
                continue
            
            # Check tags
            if tags:
                note_tag_names = {tag.name for tag in note.tags}
                if not any(tag in note_tag_names for tag in tags):
                    continue
            
            # Made it through all filters
            filtered_notes.append(note)
        
        # If we have a text query, score the notes
        results = []
        if text:
            text = text.lower()
            query_terms = set(text.split())
            
            for note in filtered_notes:
                score = 0.0
                matched_terms: Set[str] = set()
                matched_context = ""
                
                # Check title
                title_lower = note.title.lower()
                if text in title_lower:
                    score += 2.0
                    matched_context = f"Title: {note.title}"
                
                for term in query_terms:
                    if term in title_lower:
                        score += 0.5
                        matched_terms.add(term)
                
                # Check content
                content_lower = note.content.lower()
                if text in content_lower:
                    score += 1.0
                    index = content_lower.find(text)
                    start = max(0, index - 40)
                    end = min(len(content_lower), index + len(text) + 40)
                    snippet = note.content[start:end]
                    matched_context = f"Content: ...{snippet}..."
                
                for term in query_terms:
                    if term in content_lower:
                        score += 0.2
                        matched_terms.add(term)
                
                # Add to results if score is positive
                if score > 0:
                    results.append(
                        SearchResult(
                            note=note,
                            score=score,
                            matched_terms=matched_terms,
                            matched_context=matched_context
                        )
                    )
        else:
            # If no text query, just add all filtered notes with a default score
            results = [
                SearchResult(note=note, score=1.0, matched_terms=set(), matched_context="")
                for note in filtered_notes
            ]
        
        # Sort by score (descending)
        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    def batch_search_by_text(
        self, 
        queries: List[str],
        include_content: bool = True,
        include_title: bool = True,
        limit: int = 10
    ) -> BatchResult[List[SearchResult], str]:
        """Perform multiple text searches in a batch.
        
        Args:
            queries: List of search query strings
            include_content: Whether to search in content
            include_title: Whether to search in title
            limit: Maximum number of results per query
            
        Returns:
            BatchResult with results for each query
        """
        results = []
        
        for i, query in enumerate(queries):
            try:
                search_results = self.search_by_text(
                    query=query,
                    include_content=include_content,
                    include_title=include_title
                )
                
                # Apply the limit parameter
                search_results = search_results[:limit]
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=query,
                        result=search_results
                    )
                )
            except Exception as e:
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=query,
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_search_by_tag(
        self, 
        tag_queries: List[Union[str, List[str]]]
    ) -> BatchResult[List[Note], str]:
        """Perform multiple tag searches in a batch.
        
        Args:
            tag_queries: List of tag queries, each being either a string or list of strings
            
        Returns:
            BatchResult with results for each tag query
        """
        results = []
        
        for i, tags in enumerate(tag_queries):
            try:
                search_results = self.search_by_tag(tags)
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=str(tags) if isinstance(tags, str) else ",".join(tags),
                        result=search_results
                    )
                )
            except Exception as e:
                tag_id = str(tags) if isinstance(tags, str) else ",".join(tags)
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=tag_id,
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_search_by_link(
        self, 
        link_queries: List[Dict[str, str]]
    ) -> BatchResult[List[Note], str]:
        """Perform multiple link searches in a batch.
        
        Args:
            link_queries: List of dicts containing:
                - note_id: ID of the note to search from/to
                - direction: "outgoing", "incoming", or "both"
            
        Returns:
            BatchResult with results for each link query
        """
        results = []
        
        for query in link_queries:
            try:
                note_id = query.get('note_id')
                direction = query.get('direction', 'both')
                
                if not note_id:
                    raise ValueError("note_id is required")
                
                search_results = self.search_by_link(note_id, direction)
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=f"{note_id}:{direction}",
                        result=search_results
                    )
                )
            except Exception as e:
                note_id = query.get('note_id', 'unknown')
                direction = query.get('direction', 'both')
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=f"{note_id}:{direction}",
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_find_similar_notes(
        self, 
        note_ids: List[str], 
        threshold: float = 0.5
    ) -> BatchResult[List[Tuple[Note, float]], str]:
        """Find similar notes for multiple notes in a batch.
        
        Args:
            note_ids: List of note IDs to find similar notes for
            threshold: Similarity threshold
            
        Returns:
            BatchResult with similar notes for each query
        """
        results = []
        
        for note_id in note_ids:
            try:
                similar_notes = self.find_similar_notes(note_id, threshold)
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=note_id,
                        result=similar_notes
                    )
                )
            except Exception as e:
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=note_id,
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_search_combined(
        self, 
        search_queries: List[Dict[str, Any]]
    ) -> BatchResult[List[SearchResult], str]:
        """Perform multiple combined searches in a batch.
        
        Args:
            search_queries: List of dicts containing search parameters:
                - text: Optional text query
                - tags: Optional list of tags
                - note_type: Optional note type
                - start_date: Optional start date
                - end_date: Optional end date
                
        Returns:
            BatchResult with search results for each query
        """
        results = []
        
        for i, query in enumerate(search_queries):
            try:
                # Extract search parameters
                text = query.get('text')
                tags = query.get('tags')
                note_type = query.get('note_type')
                start_date = query.get('start_date')
                end_date = query.get('end_date')
                
                # Perform search
                search_results = self.search_combined(
                    text=text,
                    tags=tags,
                    note_type=note_type,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Construct a meaningful ID for this search
                components = []
                if text:
                    components.append(f"text:{text}")
                if tags:
                    components.append(f"tags:{','.join(tags)}")
                if note_type:
                    components.append(f"type:{note_type}")
                
                item_id = " AND ".join(components) if components else f"search_{i}"
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=item_id,
                        result=search_results
                    )
                )
            except Exception as e:
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=f"search_{i}",
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
