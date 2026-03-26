export class MissingOrganizationError extends Error {
  constructor() {
    super('App session requires at least one organization');
    this.name = 'MissingOrganizationError';
  }
}
