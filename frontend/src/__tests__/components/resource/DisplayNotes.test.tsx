import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DisplayNotes } from '../../../components/resource/DisplayNotes';

describe('DisplayNotes', () => {
  describe('empty state', () => {
    it('returns null when notes is null', () => {
      const { container } = render(<DisplayNotes notes={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when notes is undefined', () => {
      const { container } = render(<DisplayNotes notes={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when notes is empty array', () => {
      const { container } = render(<DisplayNotes notes={[]} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('prefixed note variants', () => {
    it('renders Danger note with danger styling', () => {
      render(
        <DisplayNotes notes={['Danger: This document is highly flammable.']} />
      );
      const note = screen.getByText(
        /Danger: This document is highly flammable/
      );
      expect(note).toBeInTheDocument();
      const wrapper = note.closest('.gbl-display-note');
      expect(wrapper).toHaveClass(
        'border-red-200',
        'bg-red-50',
        'text-red-800'
      );
    });

    it('renders Info note with info styling', () => {
      render(
        <DisplayNotes
          notes={['Info: This dataset represents the buildings.']}
        />
      );
      const note = screen.getByText(/Info: This dataset represents/);
      const wrapper = note.closest('.gbl-display-note');
      expect(wrapper).toHaveClass(
        'border-blue-200',
        'bg-blue-50',
        'text-blue-800'
      );
    });

    it('renders Tip note with tip styling', () => {
      render(<DisplayNotes notes={['Tip: Be sure to look in the mailbox.']} />);
      const note = screen.getByText(/Be sure to look in the mailbox/);
      const wrapper = note.closest('.gbl-display-note');
      expect(wrapper).toHaveClass('border-emerald-200', 'bg-emerald-50');
      expect(wrapper).toHaveAttribute(
        'aria-label',
        'Tip: Be sure to look in the mailbox.'
      );
      expect(screen.queryByText(/Tip: Be sure to look/)).not.toBeInTheDocument();
    });

    it('renders Warning note with warning styling', () => {
      render(<DisplayNotes notes={['Warning: This data is fictional.']} />);
      const note = screen.getByText(/Warning: This data is fictional/);
      const wrapper = note.closest('.gbl-display-note');
      expect(wrapper).toHaveClass('border-amber-200', 'bg-amber-50');
    });

    it('renders non-prefixed note with default styling', () => {
      render(
        <DisplayNotes notes={['This is a generic note about the resource.']} />
      );
      const note = screen.getByText(/This is a generic note/);
      const wrapper = note.closest('.gbl-display-note');
      expect(wrapper).toHaveClass(
        'border-gray-200',
        'bg-gray-50',
        'text-gray-800'
      );
    });
  });

  describe('multiple notes', () => {
    it('renders multiple notes', () => {
      render(
        <DisplayNotes notes={['Info: First note.', 'Warning: Second note.']} />
      );
      expect(screen.getByText(/Info: First note/)).toBeInTheDocument();
      expect(screen.getByText(/Warning: Second note/)).toBeInTheDocument();
      const notes = screen.getAllByRole('status');
      expect(notes).toHaveLength(2);
    });
  });

  describe('linkification', () => {
    it('linkifies URLs within display notes', () => {
      render(
        <DisplayNotes
          notes={['Info: See (https://example.com/page) for details.']}
        />
      );
      const link = screen.getByRole('link', {
        name: /https:\/\/example\.com\/page/,
      });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', 'https://example.com/page');
      expect(link).toHaveAttribute('target', '_blank');
    });
  });

  describe('accessibility', () => {
    it('has aria-label on the container', () => {
      const { container } = render(<DisplayNotes notes={['Generic note.']} />);
      const wrapper = container.querySelector(
        '[aria-label="Important notes about this data resource"]'
      );
      expect(wrapper).toBeInTheDocument();
    });

    it('each note has role="status"', () => {
      render(<DisplayNotes notes={['Note one.', 'Note two.']} />);
      const statuses = screen.getAllByRole('status');
      expect(statuses).toHaveLength(2);
    });
  });
});
